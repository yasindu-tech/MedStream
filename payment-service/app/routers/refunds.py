from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.payment import Refund, Payment, PaymentStatus
from app.schemas.payment import RefundCreate, RefundResponse
from app.services.refund_service import RefundService
from app.dependencies import (
    require_any_auth, require_admin, require_clinic_admin
)

router = APIRouter(prefix="/refunds", tags=["refunds"])

@router.post("/{payment_id}", response_model=RefundResponse, status_code=201)
async def request_refund(
    payment_id: UUID,
    data: RefundCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_any_auth)
):
    """Requests a refund for a paid payment (Patient, Admin, or Clinic Admin)."""
    # Authorization logic for request
    stmt = select(Payment).where(Payment.payment_id == payment_id)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
         raise HTTPException(status_code=404, detail="Payment not found")
         
    is_owner = str(payment.patient_id) == str(current_user["user_id"])
    is_privileged = current_user["role"] in ["admin", "clinic_admin"]
    
    if not is_owner and not is_privileged:
        raise HTTPException(status_code=403, detail="Not authorized to request refund for this payment")

    return await RefundService.request_refund(db, str(payment_id), data.reason, current_user["user_id"])

@router.patch("/{refund_id}/approve", response_model=RefundResponse)
async def approve_refund(
    refund_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """Approves a pending refund (Admin only)."""
    return await RefundService.approve_refund(db, str(refund_id), current_user["user_id"])

@router.patch("/{refund_id}/reject", response_model=RefundResponse)
async def reject_refund(
    refund_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """Rejects a pending refund (Admin only)."""
    return await RefundService.reject_refund(db, str(refund_id), current_user["user_id"])

@router.get("/payment/{payment_id}", response_model=List[RefundResponse])
async def list_refunds_for_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_any_auth)
):
    """Returns list of refunds for a payment (with ownership check)."""
    stmt = select(Payment).where(Payment.payment_id == payment_id)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
        
    is_owner = str(payment.patient_id) == str(current_user["user_id"])
    is_privileged = current_user["role"] in ["admin", "clinic_admin"]
    
    if not is_owner and not is_privileged:
        raise HTTPException(status_code=403, detail="Not authorized")

    refund_stmt = select(Refund).where(Refund.payment_id == payment_id)
    res = await db.execute(refund_stmt)
    return res.scalars().all()
