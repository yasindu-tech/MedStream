from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException
from datetime import datetime
import logging

from app.models.payment import Payment, PaymentStatus, Refund, RefundStatus, SplitStatus, PaymentSplit
from app.services.notification_client import send_notification
from app.constants import NotificationEvents
from app.services.stripe_client import StripeClient

logger = logging.getLogger(__name__)

class RefundService:
    @staticmethod
    async def request_refund(db: AsyncSession, payment_id: str, reason: str, user_id: str) -> Refund:
        """
        Creates a pending refund request.
        """
        # 1. Check payment
        stmt = select(Payment).where(Payment.payment_id == payment_id)
        result = await db.execute(stmt)
        payment = result.scalar_one_or_none()
        
        if not payment or payment.status != PaymentStatus.PAID:
            raise HTTPException(status_code=400, detail="Only paid payments can be refunded")

        # 2. Check existing active refunds
        refund_stmt = select(Refund).where(
            Refund.payment_id == payment_id,
            Refund.status.in_([RefundStatus.PENDING, RefundStatus.APPROVED, RefundStatus.PROCESSED])
        )
        res = await db.execute(refund_stmt)
        if res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="A refund request already exists for this payment")

        # 3. Create refund
        refund = Refund(
            payment_id=payment_id,
            refund_amount=payment.amount,
            reason=reason,
            status=RefundStatus.PENDING,
            requested_by=user_id
        )
        db.add(refund)
        await db.flush()
        return refund

    @staticmethod
    async def approve_refund(db: AsyncSession, refund_id: str, admin_id: str) -> Refund:
        """
        Approves a refund and reverses splits.
        """
        stmt = select(Refund).where(Refund.refund_id == refund_id)
        result = await db.execute(stmt)
        refund = result.scalar_one_or_none()
        
        if not refund or refund.status != RefundStatus.PENDING:
            raise HTTPException(status_code=400, detail="Refund request not found or not pending")

        # Get parent payment
        payment_stmt = select(Payment).where(Payment.payment_id == refund.payment_id)
        p_res = await db.execute(payment_stmt)
        payment = p_res.scalar_one()

        # 1. Update status
        refund.status = RefundStatus.APPROVED
        refund.reviewed_by = admin_id
        refund.refunded_at = datetime.utcnow()
        
        payment.status = PaymentStatus.REFUNDED
        
        # 2. Reverse splits
        await db.execute(
            update(PaymentSplit)
            .where(PaymentSplit.payment_id == payment.payment_id)
            .values(status=SplitStatus.REVERSED)
        )
        
        await db.commit()
        
        # 3. Notify
        await send_notification(
            event_type=NotificationEvents.PAYMENT_REFUNDED,
            user_id=str(payment.patient_id),
            payload={
                "refund_amount": float(refund.refund_amount),
                "currency": payment.currency,
                "reason": refund.reason
            }
        )
        
        return refund

    @staticmethod
    async def reject_refund(db: AsyncSession, refund_id: str, admin_id: str) -> Refund:
        """
        Rejects a refund request.
        """
        stmt = select(Refund).where(Refund.refund_id == refund_id)
        result = await db.execute(stmt)
        refund = result.scalar_one_or_none()
        
        if not refund or refund.status != RefundStatus.PENDING:
            raise HTTPException(status_code=400, detail="Refund request not found or not pending")

        refund.status = RefundStatus.REJECTED
        refund.reviewed_by = admin_id
        await db.commit()
        return refund
