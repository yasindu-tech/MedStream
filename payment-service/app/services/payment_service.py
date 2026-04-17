from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
import httpx
import logging

from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentCreate, MockPayRequest
from app.services.stripe_client import StripeClient
from app.services.split_service import SplitService
from app.services.notification_client import send_notification
from app.constants import NotificationEvents
from app.config import settings

logger = logging.getLogger(__name__)

class PaymentService:
    @staticmethod
    async def create_payment(db: AsyncSession, data: PaymentCreate) -> Payment:
        """
        Creates a payment record OR returns an existing idempotent record.
        """
        # 1. Check existing
        stmt = (
            select(Payment)
            .where(Payment.appointment_id == data.appointment_id)
            .options(selectinload(Payment.splits), selectinload(Payment.refunds))
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            if existing.status == PaymentStatus.paid:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Payment for this appointment has already been completed"
                )
            return existing

        # 2. Create new
        new_payment = Payment(
            **data.model_dump(),
            status=PaymentStatus.pending,
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        db.add(new_payment)
        await db.commit() # Ensure immediate visibility for follow-up API calls
        
        # Reload with relationships for the response model
        stmt = (
            select(Payment)
            .where(Payment.payment_id == new_payment.payment_id)
            .options(selectinload(Payment.splits), selectinload(Payment.refunds))
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def initiate_payment(db: AsyncSession, payment_id: str, patient_email: str, user_id: str) -> dict:
        """
        Initiates a Stripe Checkout Session.
        """
        stmt = (
            select(Payment)
            .where(Payment.payment_id == payment_id)
            .options(selectinload(Payment.splits), selectinload(Payment.refunds))
        )
        result = await db.execute(stmt)
        payment = result.scalar_one_or_none()

        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        # Ownership check
        if str(payment.patient_id) != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to initiate this payment")

        # 1. Check expiration
        if payment.expires_at and payment.expires_at < datetime.now(timezone.utc):
            payment.status = PaymentStatus.expired
            await db.commit()
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Payment link has expired")

        if payment.status not in [PaymentStatus.pending, PaymentStatus.failed]:
            raise HTTPException(status_code=400, detail=f"Payment cannot be initiated in status {payment.status}")

        # 2. Call Stripe
        try:
            # Fetch appointment details for display on Stripe
            doctor_name = "Doctor"
            appointment_date = ""
            try:
                appt_url = f"{settings.APPOINTMENT_SERVICE_URL}/internal/appointments/{payment.appointment_id}"
                async with httpx.AsyncClient(timeout=5.0) as client:
                    appt_resp = await client.get(appt_url)
                    if appt_resp.status_code == 200:
                        appt_data = appt_resp.json()
                        doctor_name = appt_data.get("doctor_name", "Doctor")
                        appointment_date = f"{appt_data.get('appointment_date')} {appt_data.get('start_time')}"
            except Exception as e:
                logger.warning(f"Could not fetch appointment details for Stripe display: {e}")

            if settings.ENABLE_STRIPE_MOCK:
                mock_session_id = f"mock_ss_{payment_id}"
                mock_url = settings.STRIPE_SUCCESS_URL.replace("{CHECKOUT_SESSION_ID}", mock_session_id)
                session = {"id": mock_session_id, "url": mock_url}
                logger.info(f"Using MOCK payment session for payment {payment_id}")
            else:
                if not settings.STRIPE_API_KEY:
                    raise ValueError("STRIPE_API_KEY not configured and Mock Mode is disabled")
                    
                session = StripeClient.create_checkout_session(
                    appointment_id=str(payment.appointment_id),
                    amount=payment.amount,
                    currency=payment.currency,
                    patient_email=patient_email,
                    doctor_name=doctor_name,
                    appointment_date=appointment_date
                )
            
            payment.status = PaymentStatus.processing
            payment.transaction_reference = session["id"]
            await db.commit()
            
            return {
                "payment_id": payment.payment_id,
                "gateway_url": session["url"],
                "transaction_reference": session["id"],
                "expires_at": payment.expires_at
            }
        except Exception as e:
            logger.error(f"Payment initiation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize payment gateway: {str(e)}")

    @staticmethod
    async def verify_and_confirm_session(db: AsyncSession, session_id: str):
        """
        Manually verifies a session status and confirms if paid.
        Allows webhook-less operation for local dev/viva.
        """
        # Handle Mock Mode
        if settings.ENABLE_STRIPE_MOCK and session_id.startswith("mock_ss_"):
            payment_id_str = session_id.replace("mock_ss_", "")
            try:
                payment_id = UUID(payment_id_str)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid mock session ID")
                
            stmt = select(Payment).where(Payment.payment_id == payment_id)
            result = await db.execute(stmt)
            payment = result.scalar_one_or_none()
            
            if not payment:
                raise HTTPException(status_code=404, detail="Payment not found for mock session")
                
            if payment.status != PaymentStatus.paid:
                await PaymentService.confirm_payment(db, payment, f"mock_tx_{payment_id}")
                await db.commit()
            return {"status": "paid", "payment_id": str(payment.payment_id)}

        # Handle Real Stripe
        try:
            session = StripeClient.retrieve_checkout_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Stripe session not found")
                
            if session["payment_status"] == "paid":
                # Find matching payment record
                stmt = select(Payment).where(Payment.transaction_reference == session_id)
                result = await db.execute(stmt)
                payment = result.scalar_one_or_none()
                
                if not payment:
                    # Try metadata as fallback
                    appt_id = session["metadata"].get("appointment_id")
                    if appt_id:
                        stmt = select(Payment).where(Payment.appointment_id == UUID(appt_id))
                        result = await db.execute(stmt)
                        payment = result.scalar_one_or_none()
                
                if payment:
                    if payment.status != PaymentStatus.paid:
                        await PaymentService.confirm_payment(db, payment, session_id)
                        await db.commit()
                    return {"status": "paid", "payment_id": str(payment.payment_id)}
                else:
                    return {"status": "unlinked_paid", "message": "Payment confirmed on Stripe but record not found locally"}
            
            return {"status": session["payment_status"], "message": "Session not yet paid"}
            
        except Exception as e:
            logger.error(f"Session verification failed: {e}")
            raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

    @staticmethod
    async def confirm_payment(db: AsyncSession, payment: Payment, transaction_id: str):
        """
        Finalizes a payment after successful callback/webhook.
        """
        if payment.status == PaymentStatus.paid:
            return

        payment.status = PaymentStatus.paid
        payment.paid_at = datetime.utcnow()
        payment.transaction_reference = transaction_id
        
        # 1. Create splits
        await SplitService.create_splits(db, payment)
        
        await db.commit()
        
        # 2. Callback to appointment-service to confirm the appointment
        await PaymentService._notify_appointment_service(
            appointment_id=str(payment.appointment_id),
            payment_status="paid",
            transaction_reference=transaction_id,
        )
        
        # 3. Notify patient (Fire and forget)
        await send_notification(
            event_type=NotificationEvents.PAYMENT_CONFIRMED,
            user_id=str(payment.patient_id),
            payload={
                "patient_name": "Valued Patient",
                "amount": float(payment.amount),
                "currency": payment.currency,
                "transaction_reference": transaction_id,
                "appointment_id": str(payment.appointment_id)
            },
            channels=["email", "in_app"],
        )
        
        # Notify appointment booked (final confirmation)
        await send_notification(
            event_type=NotificationEvents.APPOINTMENT_BOOKED,
            user_id=str(payment.patient_id),
            payload={
                "appointment_id": str(payment.appointment_id),
                "status": "confirmed"
            },
            channels=["email", "in_app"],
        )

    @staticmethod
    async def fail_payment(db: AsyncSession, payment: Payment, reason: str):
        """
        Handles payment failure.
        """
        payment.status = PaymentStatus.failed
        payment.failure_reason = reason
        payment.retry_count += 1
        
        await db.commit()
        
        # Callback to appointment-service to mark payment as failed
        await PaymentService._notify_appointment_service(
            appointment_id=str(payment.appointment_id),
            payment_status="failed",
            transaction_reference=None,
        )
        
        # Notify failure
        await send_notification(
            event_type=NotificationEvents.PAYMENT_FAILED,
            user_id=str(payment.patient_id),
            payload={
                "amount": float(payment.amount),
                "currency": payment.currency,
                "reason": reason,
                "retry_count": payment.retry_count,
                "retries_remaining": payment.max_retries - payment.retry_count
            },
            channels=["email", "in_app"],
        )

    @staticmethod
    async def _notify_appointment_service(
        appointment_id: str,
        payment_status: str,
        transaction_reference: str | None,
    ):
        """Fire-and-forget callback to appointment-service to sync payment status."""
        url = f"{settings.APPOINTMENT_SERVICE_URL}/internal/appointments/{appointment_id}/payment-status"
        body = {
            "payment_status": payment_status,
            "transaction_reference": transaction_reference,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.patch(url, json=body)
                resp.raise_for_status()
                logger.info(f"Appointment {appointment_id} payment status updated to {payment_status}")
        except Exception as exc:
            logger.error(f"Failed to notify appointment-service for {appointment_id}: {exc}")
