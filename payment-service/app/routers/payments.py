from fastapi import APIRouter, Depends, HTTPException, Request, Query, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional
from uuid import UUID
import logging
import stripe

from app.database import get_db
from app.models.payment import Payment, PaymentStatus, PaymentSplit, Refund
from app.schemas.payment import (
    PaymentCreate, PaymentResponse, PaymentInitiateResponse, MockPayRequest
)
from app.services.payment_service import PaymentService
from app.services.stripe_client import StripeClient
from app.dependencies import (
    require_patient, require_admin, require_clinic_admin, require_any_auth
)
from app.config import settings

router = APIRouter(tags=["payments"])

logger = logging.getLogger(__name__)

"""
HOW OTHER SERVICES CALL THE PAYMENT SERVICE
--------------------------------------------
Base URL (internal): http://payment-service:8006
Auth: Bearer JWT required on all endpoints except /webhook and /health.

--- Appointment-service calls after booking ---
POST http://payment-service:8006/api/payments/
Headers: Authorization: Bearer <system-jwt>
Body:
{
  "appointment_id": "<uuid>",
  "patient_id": "<uuid>",
  "doctor_id": "<uuid>",
  "clinic_id": "<uuid>",
  "amount": 2500.00,
  "currency": "USD"
}
Response: { payment_id, status: "pending", ... }
"""

@router.post("/", response_model=PaymentResponse, status_code=201)
async def create_payment(
    data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_any_auth)
):
    """Creates a new payment record or returns existing one (idempotent)."""
    return await PaymentService.create_payment(db, data)

@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_any_auth)
):
    """Returns a full payment record with splits and refunds."""
    stmt = select(Payment).where(Payment.payment_id == payment_id)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Ownership check
    is_owner = str(payment.patient_id) == str(current_user["user_id"])
    is_privileged = current_user["role"] in ["admin", "clinic_admin"]
    
    if not is_owner and not is_privileged:
        raise HTTPException(status_code=403, detail="Not authorized to view this payment")

    return payment

@router.get("/appointment/{appointment_id}", response_model=PaymentResponse)
async def get_payment_by_appointment(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_any_auth)
):
    """Returns payment record for a given appointment."""
    stmt = select(Payment).where(Payment.appointment_id == appointment_id)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found for this appointment")

    # Ownership check
    is_owner = str(payment.patient_id) == str(current_user["user_id"])
    is_privileged = current_user["role"] in ["admin", "clinic_admin"]
    
    if not is_owner and not is_privileged:
        raise HTTPException(status_code=403, detail="Not authorized to view this payment")

    return payment

@router.get("/", response_model=List[PaymentResponse])
async def list_payments(
    status_filter: Optional[PaymentStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_any_auth)
):
    """Lists payments based on role and filters."""
    query = select(Payment).order_by(desc(Payment.created_at))

    if current_user["role"] == "patient":
        query = query.where(Payment.patient_id == UUID(current_user["user_id"]))
    elif current_user["role"] == "clinic_admin":
        if not current_user.get("clinic_id"):
             raise HTTPException(status_code=400, detail="Clinic ID missing from token")
        query = query.where(Payment.clinic_id == UUID(current_user["clinic_id"]))
    # Admin sees all

    if status_filter:
        query = query.where(Payment.status == status_filter)

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/{payment_id}/initiate", response_model=PaymentInitiateResponse)
async def initiate_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_patient)
):
    """Initiates a Stripe Checkout session for a pending payment."""
    return await PaymentService.initiate_payment(db, str(payment_id), current_user["email"])

@router.post("/{payment_id}/retry", response_model=PaymentResponse)
async def retry_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_patient)
):
    """Resets a failed payment for retry if limit not reached."""
    stmt = select(Payment).where(Payment.payment_id == payment_id, Payment.patient_id == UUID(current_user["user_id"]))
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != PaymentStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only failed payments can be retried")

    if payment.retry_count >= payment.max_retries:
        raise HTTPException(status_code=400, detail="Maximum retry limit reached")

    payment.status = PaymentStatus.PENDING
    payment.transaction_reference = None
    await db.commit()
    return payment

@router.post("/webhook", status_code=200)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db)
):
    """Async endpoint for Stripe webhook events."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=500, detail="Webhook configuration missing")

    payload = await request.body()
    try:
        event = StripeClient.verify_webhook(payload, stripe_signature)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle events
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        transaction_id = session['id']
        
        # We store checkout session ID in transaction_reference during initiate
        stmt = select(Payment).where(Payment.transaction_reference == transaction_id)
        result = await db.execute(stmt)
        payment = result.scalar_one_or_none()
        
        if payment:
            await PaymentService.confirm_payment(db, payment, transaction_id)
        else:
            logger.warning(f"Payment not found for session {transaction_id}")

    elif event['type'] in ['payment_intent.payment_failed', 'invoice.payment_failed']:
        session = event['data']['object']
        transaction_id = session.get('id')
        reason = session.get('last_payment_error', {}).get('message', 'Unknown stripe failure')
        
        stmt = select(Payment).where(Payment.transaction_reference == transaction_id)
        result = await db.execute(stmt)
        payment = result.scalar_one_or_none()
        
        if payment:
            await PaymentService.fail_payment(db, payment, reason)

    return {"status": "success"}

@router.get("/{payment_id}/receipt")
async def get_receipt(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_any_auth)
):
    """Returns a JSON receipt for a paid payment."""
    stmt = select(Payment).where(Payment.payment_id == payment_id, Payment.status == PaymentStatus.PAID)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Paid payment not found")

    # Ownership check
    if str(payment.patient_id) != str(current_user["user_id"]) and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    # Fetch splits
    split_stmt = select(PaymentSplit).where(PaymentSplit.payment_id == payment_id)
    split_res = await db.execute(split_stmt)
    splits = split_res.scalars().all()

    return {
        "receipt_id": payment.payment_id,
        "payment_id": payment.payment_id,
        "appointment_id": payment.appointment_id,
        "patient_id": payment.patient_id,
        "doctor_id": payment.doctor_id,
        "clinic_id": payment.clinic_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "transaction_reference": payment.transaction_reference,
        "paid_at": payment.paid_at,
        "generated_at": datetime.utcnow(),
        "splits": splits
    }
