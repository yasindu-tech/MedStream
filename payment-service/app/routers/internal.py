from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.payment import Payment, PaymentSplit, SplitType, SplitStatus, PaymentStatus, Refund, RefundStatus
from app.schemas.payment import PlatformSummary, ClinicSummary

router = APIRouter(tags=["internal"])


@router.get("/summaries/clinic/{clinic_id}", response_model=ClinicSummary)
async def internal_clinic_summary(
    clinic_id: UUID,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    db: AsyncSession = Depends(get_db),
) -> ClinicSummary:
    payment_query = select(Payment).where(Payment.clinic_id == clinic_id)
    if from_date:
        payment_query = payment_query.where(Payment.created_at >= from_date)
    if to_date:
        payment_query = payment_query.where(Payment.created_at <= to_date)

    payment_result = await db.execute(payment_query)
    payments = payment_result.scalars().all()

    total_revenue = sum((p.amount for p in payments if p.status == PaymentStatus.paid), Decimal("0"))
    total_failed = sum((p.amount for p in payments if p.status == PaymentStatus.failed), Decimal("0"))

    refund_query = (
        select(func.sum(Refund.refund_amount).label("total_refunded"))
        .join(Payment, Payment.payment_id == Refund.payment_id)
        .where(
            Payment.clinic_id == clinic_id,
            Refund.status == RefundStatus.approved,
        )
    )
    if from_date:
        refund_query = refund_query.where(Refund.created_at >= from_date)
    if to_date:
        refund_query = refund_query.where(Refund.created_at <= to_date)

    refund_res = await db.execute(refund_query)
    total_refunded = refund_res.scalar() or 0

    split_query = select(func.sum(PaymentSplit.amount)).where(
        PaymentSplit.split_type == SplitType.clinic,
        PaymentSplit.beneficiary_id == clinic_id,
        PaymentSplit.status != SplitStatus.reversed,
    )
    split_res = await db.execute(split_query)
    clinic_share_total = split_res.scalar() or 0

    return {
        "total_revenue": total_revenue,
        "total_refunded": total_refunded,
        "total_failed": total_failed,
        "clinic_share_total": clinic_share_total,
        "period_start": from_date,
        "period_end": to_date,
    }


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
