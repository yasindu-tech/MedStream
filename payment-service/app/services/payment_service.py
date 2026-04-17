from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
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
        stmt = select(Payment).where(Payment.appointment_id == data.appointment_id)
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
        await db.refresh(new_payment)
        return new_payment

    @staticmethod
    async def initiate_payment(db: AsyncSession, payment_id: str, patient_email: str, user_id: str) -> dict:
        """
        Initiates a Stripe Checkout Session.
        """
        stmt = select(Payment).where(Payment.payment_id == payment_id)
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
                    patient_email=patient_email
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
    async def confirm_payment(db: AsyncSession, payment: Payment, transaction_id: str):
        """
        Finalizes a payment after successful gateway callback/webhook.
        """
        if payment.status == PaymentStatus.paid:
            return

        payment.status = PaymentStatus.paid
        payment.paid_at = datetime.utcnow()
        payment.transaction_reference = transaction_id
        
        # 1. Create splits
        await SplitService.create_splits(db, payment)
        
        await db.commit()
        
        # 2. Notify (Fire and forget)
        await send_notification(
            event_type=NotificationEvents.PAYMENT_CONFIRMED,
            user_id=str(payment.patient_id),
            payload={
                "patient_name": "Valued Patient", # We don't have user names in this DB
                "amount": float(payment.amount),
                "currency": payment.currency,
                "transaction_reference": transaction_id,
                "appointment_id": str(payment.appointment_id)
            }
        )
        
        # Notify appointment booked (final confirmation)
        await send_notification(
            event_type=NotificationEvents.APPOINTMENT_BOOKED,
            user_id=str(payment.patient_id),
            payload={
                "appointment_id": str(payment.appointment_id),
                "status": "confirmed"
            }
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
            }
        )
