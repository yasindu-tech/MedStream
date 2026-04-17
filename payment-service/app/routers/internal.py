from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.payment import Payment, PaymentSplit, SplitType, SplitStatus, PaymentStatus, Refund, RefundStatus
from app.schemas.payment import PlatformSummary

router = APIRouter(tags=["internal"])


@router.get("/summaries/platform", response_model=PlatformSummary)
async def internal_platform_summary(db: AsyncSession = Depends(get_db)) -> PlatformSummary:
    stats_res = await db.execute(
        select(
            func.sum(Payment.amount).label("total_rev"),
            func.count(Payment.payment_id).label("total_count"),
        ).where(Payment.status == PaymentStatus.paid)
    )
    rev_stats = stats_res.first()

    refund_res = await db.execute(
        select(
            func.sum(Refund.refund_amount).label("total_refunded"),
            func.count(Refund.refund_id).label("refund_count"),
        ).where(Refund.status == RefundStatus.approved)
    )
    ref_stats = refund_res.first()

    failed_res = await db.execute(select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.failed))
    pending_res = await db.execute(select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.pending))

    comm_res = await db.execute(
        select(func.sum(PaymentSplit.amount)).where(
            PaymentSplit.split_type == SplitType.platform,
            PaymentSplit.status != SplitStatus.reversed,
        )
    )

    return {
        "total_revenue": rev_stats.total_rev or 0,
        "total_refunded": ref_stats.total_refunded or 0,
        "total_failed": failed_res.scalar() or 0,
        "total_pending": pending_res.scalar() or 0,
        "platform_commission_total": comm_res.scalar() or 0,
        "payment_count": rev_stats.total_count or 0,
        "refund_count": ref_stats.refund_count or 0,
    }
