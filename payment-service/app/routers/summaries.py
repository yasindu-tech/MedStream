from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from app.database import get_db
from app.models.payment import Payment, PaymentSplit, SplitType, SplitStatus, PaymentStatus, Refund
from app.schemas.payment import MyEarningsSummary, ClinicSummary, PlatformSummary
from app.dependencies import require_doctor, require_clinic_admin, require_admin

router = APIRouter(prefix="/summaries", tags=["summaries"])

@router.get("/my-earnings", response_model=MyEarningsSummary)
async def get_doctor_earnings(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_doctor)
):
    """Returns earnings summary for the logged-in doctor."""
    doctor_id = UUID(current_user["user_id"])
    
    stmt = select(PaymentSplit).where(
        PaymentSplit.split_type == SplitType.DOCTOR,
        PaymentSplit.beneficiary_id == doctor_id
    )
    result = await db.execute(stmt)
    splits = result.scalars().all()
    
    total_earned = sum((s.amount for s in splits if s.status == SplitStatus.SETTLED), Decimal("0"))
    total_pending = sum((s.amount for s in splits if s.status == SplitStatus.PENDING), Decimal("0"))
    total_reversed = sum((s.amount for s in splits if s.status == SplitStatus.REVERSED), Decimal("0"))
    
    return {
        "total_earned": total_earned,
        "total_pending": total_pending,
        "total_reversed": total_reversed,
        "splits": splits
    }

@router.get("/clinic", response_model=ClinicSummary)
async def get_clinic_summary(
    clinic_id: Optional[UUID] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_clinic_admin)
):
    """Returns financial summary for a clinic."""
    target_clinic_id = clinic_id or (UUID(current_user["clinic_id"]) if current_user.get("clinic_id") else None)
    
    if not target_clinic_id:
        raise HTTPException(status_code=400, detail="Clinic ID is required")
        
    if current_user["role"] == "clinic_admin" and str(target_clinic_id) != str(current_user.get("clinic_id")):
        raise HTTPException(status_code=403, detail="Not authorized to view other clinic summaries")

    # Base query for clinic payments
    query = select(Payment).where(Payment.clinic_id == target_clinic_id)
    if from_date:
        query = query.where(Payment.created_at >= from_date)
    if to_date:
        query = query.where(Payment.created_at <= to_date)
        
    result = await db.execute(query)
    payments = result.scalars().all()
    
    total_revenue = sum((p.amount for p in payments if p.status == PaymentStatus.PAID), Decimal("0"))
    total_refunded = sum((p.amount for p in payments if p.status == PaymentStatus.REFUNDED), Decimal("0"))
    total_failed = sum((p.amount for p in payments if p.status == PaymentStatus.FAILED), Decimal("0"))
    
    # Calculate clinic share from splits
    split_stmt = select(func.sum(PaymentSplit.amount)).where(
        PaymentSplit.split_type == SplitType.CLINIC,
        PaymentSplit.beneficiary_id == target_clinic_id,
        PaymentSplit.status != SplitStatus.REVERSED
    )
    split_res = await db.execute(split_stmt)
    clinic_share_total = split_res.scalar() or Decimal("0")
    
    return {
        "total_revenue": total_revenue,
        "total_refunded": total_refunded,
        "total_failed": total_failed,
        "clinic_share_total": clinic_share_total,
        "period_start": from_date,
        "period_end": to_date
    }

@router.get("/platform", response_model=PlatformSummary)
async def get_platform_summary(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_admin)
):
    """Returns platform-wide financial aggregates (Admin only)."""
    # Revenue stats
    stats_res = await db.execute(
        select(
            func.sum(Payment.amount).label("total_rev"),
            func.count(Payment.payment_id).label("total_count")
        ).where(Payment.status == PaymentStatus.PAID)
    )
    rev_stats = stats_res.first()
    
    # Refund stats
    refund_res = await db.execute(
        select(
            func.sum(Refund.refund_amount).label("total_refunded"),
            func.count(Refund.refund_id).label("refund_count")
        ).where(Refund.status == "approved") # Use string for enum if needed or Enum class
    )
    ref_stats = refund_res.first()
    
    # Failed & Pending
    failed_res = await db.execute(select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.FAILED))
    pending_res = await db.execute(select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.PENDING))
    
    # Platform Commission
    comm_res = await db.execute(
        select(func.sum(PaymentSplit.amount)).where(
            PaymentSplit.split_type == SplitType.PLATFORM,
            PaymentSplit.status != SplitStatus.REVERSED
        )
    )
    
    return {
        "total_revenue": rev_stats.total_rev or Decimal("0"),
        "total_refunded": ref_stats.total_refunded or Decimal("0"),
        "total_failed": failed_res.scalar() or Decimal("0"),
        "total_pending": pending_res.scalar() or Decimal("0"),
        "platform_commission_total": comm_res.scalar() or Decimal("0"),
        "payment_count": rev_stats.total_count or 0,
        "refund_count": ref_stats.refund_count or 0
    }
