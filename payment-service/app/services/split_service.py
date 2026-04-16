from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.models.payment import Payment, PaymentSplit, SplitType, SplitStatus
from app.config import settings
from app.constants import PLATFORM_BENEFICIARY_ID

logger = logging.getLogger(__name__)

class SplitService:
    @staticmethod
    def _calculate_amount(total_amount: Decimal, percentage: float) -> Decimal:
        """Helper to calculate split amount with proper rounding."""
        return (total_amount * Decimal(str(percentage)) / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @staticmethod
    async def create_splits(db: AsyncSession, payment: Payment):
        """
        Creates the platform, clinic, and doctor splits for a successful payment.
        """
        logger.info(f"Calculating splits for payment {payment.payment_id}")
        
        # 1. Platform Split
        platform_amount = SplitService._calculate_amount(
            payment.amount, settings.PLATFORM_COMMISSION_PCT
        )
        db.add(PaymentSplit(
            payment_id=payment.payment_id,
            split_type=SplitType.platform,
            beneficiary_id=PLATFORM_BENEFICIARY_ID,
            percentage=settings.PLATFORM_COMMISSION_PCT,
            amount=platform_amount,
            status=SplitStatus.pending
        ))

        # 2. Clinic Split
        if payment.clinic_id:
            clinic_amount = SplitService._calculate_amount(
                payment.amount, settings.CLINIC_SHARE_PCT
            )
            db.add(PaymentSplit(
                payment_id=payment.payment_id,
                split_type=SplitType.clinic,
                beneficiary_id=payment.clinic_id,
                percentage=settings.CLINIC_SHARE_PCT,
                amount=clinic_amount,
                status=SplitStatus.pending
            ))

        # 3. Doctor Split
        doctor_amount = SplitService._calculate_amount(
            payment.amount, settings.DOCTOR_SHARE_PCT
        )
        db.add(PaymentSplit(
            payment_id=payment.payment_id,
            split_type=SplitType.doctor,
            beneficiary_id=payment.doctor_id,
            percentage=settings.DOCTOR_SHARE_PCT,
            amount=doctor_amount,
            status=SplitStatus.pending
        ))

        await db.flush()
        logger.info(f"Splits created for payment {payment.payment_id}")
