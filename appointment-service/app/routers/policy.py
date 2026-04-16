"""Appointment policy management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import AppointmentPolicyResponse, UpdateAppointmentPolicyRequest
from app.services.policy import get_or_create_active_policy, resolve_effective_policy, update_active_policy

router = APIRouter(prefix="/admin/policies", tags=["Appointment Policies"])


@router.get("/active", response_model=AppointmentPolicyResponse)
def get_active_policy(
    user: dict = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> AppointmentPolicyResponse:
    policy = get_or_create_active_policy(db)
    return AppointmentPolicyResponse(
        policy_id=policy.policy_id,
        cancellation_window_hours=policy.cancellation_window_hours,
        reschedule_window_hours=policy.reschedule_window_hours,
        advance_booking_days=policy.advance_booking_days,
        no_show_grace_period_minutes=policy.no_show_grace_period_minutes,
        max_reschedules=policy.max_reschedules,
        is_active=policy.is_active,
        created_by=policy.created_by,
        created_at=policy.created_at.isoformat() if policy.created_at else "",
        updated_at=policy.updated_at.isoformat() if policy.updated_at else "",
    )


@router.put("/active", response_model=AppointmentPolicyResponse)
def put_active_policy(
    request: UpdateAppointmentPolicyRequest,
    user: dict = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> AppointmentPolicyResponse:
    policy = update_active_policy(db, request=request, changed_by=f"admin:{user['sub']}")
    return AppointmentPolicyResponse(
        policy_id=policy.policy_id,
        cancellation_window_hours=policy.cancellation_window_hours,
        reschedule_window_hours=policy.reschedule_window_hours,
        advance_booking_days=policy.advance_booking_days,
        no_show_grace_period_minutes=policy.no_show_grace_period_minutes,
        max_reschedules=policy.max_reschedules,
        is_active=policy.is_active,
        created_by=policy.created_by,
        created_at=policy.created_at.isoformat() if policy.created_at else "",
        updated_at=policy.updated_at.isoformat() if policy.updated_at else "",
    )


@router.get("/effective")
def get_effective_policy_for_runtime(
    db: Session = Depends(get_db),
) -> dict:
    policy = resolve_effective_policy(db)
    return {
        "policy_id": policy.policy_id,
        "cancellation_window_hours": policy.cancellation_window_hours,
        "reschedule_window_hours": policy.reschedule_window_hours,
        "advance_booking_days": policy.advance_booking_days,
        "no_show_grace_period_minutes": policy.no_show_grace_period_minutes,
        "max_reschedules": policy.max_reschedules,
    }
