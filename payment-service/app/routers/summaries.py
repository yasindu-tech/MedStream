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
import httpx
from app.config import settings

router = APIRouter(prefix="/summaries", tags=["summaries"])

@router.get("/my-earnings", response_model=MyEarningsSummary)
async def get_doctor_earnings(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_doctor)
):
    """Returns earnings summary for the logged-in doctor."""
    user_id = current_user["user_id"]
    
    # Resolve user_id to doctor_id via doctor-service
    doctor_id = None
    try:
        url = f"{settings.DOCTOR_SERVICE_URL}/internal/doctors/by-user/{user_id}"
        headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                doctor_id = UUID(resp.json()["doctor_id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not resolve doctor profile")
        
    if not doctor_id:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    
    stmt = select(PaymentSplit).where(
        PaymentSplit.split_type == SplitType.doctor,
        PaymentSplit.beneficiary_id == doctor_id
    )
    result = await db.execute(stmt)
    splits = result.scalars().all()
    
    total_earned = sum((s.amount for s in splits if s.status == SplitStatus.settled), Decimal("0"))
    total_pending = sum((s.amount for s in splits if s.status == SplitStatus.pending), Decimal("0"))
    total_reversed = sum((s.amount for s in splits if s.status == SplitStatus.reversed), Decimal("0"))
    
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
    
    if not target_clinic_id and current_user["role"] in ["clinic_admin", "clinic_staff"]:
        try:
            url = f"{settings.CLINIC_SERVICE_URL}/internal/staff/{current_user['user_id']}/clinic"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    target_clinic_id = UUID(resp.json()["clinic_id"])
        except Exception:
            pass

    if not target_clinic_id:
        raise HTTPException(status_code=400, detail="Clinic ID is required or not found")
        
    if current_user["role"] == "clinic_admin" and clinic_id is not None and str(target_clinic_id) != str(clinic_id):
        raise HTTPException(status_code=403, detail="Not authorized to view other clinic summaries")

    # Base query for clinic payments
    query = select(Payment).where(Payment.clinic_id == target_clinic_id)
    if from_date:
        query = query.where(Payment.created_at >= from_date)
    if to_date:
        query = query.where(Payment.created_at <= to_date)
        
    result = await db.execute(query)
    payments = result.scalars().all()
    
    total_revenue = sum((p.amount for p in payments if p.status == PaymentStatus.paid), Decimal("0"))
    total_refunded = sum((p.amount for p in payments if p.status == PaymentStatus.refunded), Decimal("0"))
    total_failed = sum((p.amount for p in payments if p.status == PaymentStatus.failed), Decimal("0"))
    
    # Calculate clinic share from splits
    split_stmt = select(func.sum(PaymentSplit.amount)).where(
        PaymentSplit.split_type == SplitType.clinic,
        PaymentSplit.beneficiary_id == target_clinic_id,
        PaymentSplit.status != SplitStatus.reversed
    )
    if from_date:
        split_stmt = split_stmt.where(PaymentSplit.created_at >= from_date)
    if to_date:
        split_stmt = split_stmt.where(PaymentSplit.created_at <= to_date)

    split_res = await db.execute(split_stmt)
    clinic_share_total = split_res.scalar() or Decimal("0")
    
    total_bookings = len([p for p in payments if p.status == PaymentStatus.paid])

    return {
        "total_revenue": total_revenue,
        "total_refunded": total_refunded,
        "total_failed": total_failed,
        "clinic_share_total": clinic_share_total,
        "total_bookings": total_bookings,
        "period_start": from_date,
        "period_end": to_date
    }

@router.get("/platform", response_model=PlatformSummary)
async def get_platform_summary(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_admin)
):
    """Returns platform-wide financial aggregates (Admin only)."""
    # Revenue stats (Total paid volume)
    rev_stmt = select(
        func.sum(Payment.amount).label("total_rev"),
        func.count(Payment.payment_id).label("total_count"),
        func.count(func.distinct(Payment.patient_id)).label("unique_patients")
    ).where(Payment.status == PaymentStatus.paid)
    
    rev_stats_res = await db.execute(rev_stmt)
    rev_stats = rev_stats_res.first()
    
    # Refund stats
    refund_res = await db.execute(
        select(
            func.sum(Refund.refund_amount).label("total_refunded"),
            func.count(Refund.refund_id).label("refund_count")
        ).where(Refund.status == "approved")
    )
    ref_stats = refund_res.first()
    
    # Failed, Pending (Processing)
    failed_res = await db.execute(select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.failed))
    pending_res = await db.execute(select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.pending))
    
    # Platform Commission (Settled)
    settled_comm_res = await db.execute(
        select(func.sum(PaymentSplit.amount)).where(
            PaymentSplit.split_type == SplitType.platform,
            PaymentSplit.status == SplitStatus.settled
        )
    )
    platform_settled = settled_comm_res.scalar() or Decimal("0")

    # Platform Commission (Processing/Pending)
    pending_comm_res = await db.execute(
        select(func.sum(PaymentSplit.amount)).where(
            PaymentSplit.split_type == SplitType.platform,
            PaymentSplit.status == SplitStatus.pending
        )
    )
    platform_pending = pending_comm_res.scalar() or Decimal("0")
    
    total_rev = rev_stats.total_rev or Decimal("0")
    total_refunded = ref_stats.total_refunded or Decimal("0")
    
    return {
        "total_revenue": total_rev,
        "platform_earnings": platform_settled, # Main earning is settled commission
        "distinct_patients": rev_stats.unique_patients or 0,
        "total_payments": rev_stats.total_count or 0,
        "total_refunded": total_refunded,
        "total_failed": failed_res.scalar() or Decimal("0"), # Keeping gross failed for context
        "total_settled": platform_settled, # Now returning the platform share version
        "total_processing": platform_pending, # Now returning the platform share version
        "refund_count": ref_stats.refund_count or 0
    }
