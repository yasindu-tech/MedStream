"""Dynamic appointment policy management and resolution."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AppointmentPolicy, AppointmentPolicyHistory
from app.schemas import UpdateAppointmentPolicyRequest


@dataclass
class EffectivePolicy:
    policy_id: str | None
    cancellation_window_hours: int
    reschedule_window_hours: int
    advance_booking_days: int
    no_show_grace_period_minutes: int
    max_reschedules: int


def get_or_create_active_policy(db: Session) -> AppointmentPolicy:
    policy = (
        db.query(AppointmentPolicy)
        .filter(AppointmentPolicy.is_active.is_(True))
        .order_by(AppointmentPolicy.created_at.desc())
        .first()
    )
    if policy:
        return policy

    policy = AppointmentPolicy(
        cancellation_window_hours=settings.CANCELLATION_WINDOW_HOURS,
        reschedule_window_hours=settings.RESCHEDULE_WINDOW_HOURS,
        advance_booking_days=settings.ADVANCE_BOOKING_DAYS,
        no_show_grace_period_minutes=settings.NO_SHOW_GRACE_PERIOD_MINUTES,
        max_reschedules=settings.MAX_RESCHEDULES,
        is_active=True,
        created_by="system",
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def resolve_effective_policy(db: Session) -> EffectivePolicy:
    policy = get_or_create_active_policy(db)
    return EffectivePolicy(
        policy_id=str(policy.policy_id),
        cancellation_window_hours=policy.cancellation_window_hours,
        reschedule_window_hours=policy.reschedule_window_hours,
        advance_booking_days=policy.advance_booking_days,
        no_show_grace_period_minutes=policy.no_show_grace_period_minutes,
        max_reschedules=policy.max_reschedules,
    )


def resolve_policy_for_appointment(db: Session, policy_id: UUID | None) -> EffectivePolicy:
    """
    Resolve policy bound to an existing appointment if available.

    Falls back to currently active policy when a snapshot is not present,
    preserving backward compatibility for legacy rows.
    """
    if policy_id:
        policy = (
            db.query(AppointmentPolicy)
            .filter(AppointmentPolicy.policy_id == policy_id)
            .first()
        )
        if policy:
            return EffectivePolicy(
                policy_id=str(policy.policy_id),
                cancellation_window_hours=policy.cancellation_window_hours,
                reschedule_window_hours=policy.reschedule_window_hours,
                advance_booking_days=policy.advance_booking_days,
                no_show_grace_period_minutes=policy.no_show_grace_period_minutes,
                max_reschedules=policy.max_reschedules,
            )

    return resolve_effective_policy(db)


def update_active_policy(
    db: Session,
    *,
    request: UpdateAppointmentPolicyRequest,
    changed_by: str,
) -> AppointmentPolicy:
    _validate_policy_values(request)

    old_policy = get_or_create_active_policy(db)
    old_policy.is_active = False

    new_policy = AppointmentPolicy(
        cancellation_window_hours=request.cancellation_window_hours,
        reschedule_window_hours=request.reschedule_window_hours,
        advance_booking_days=request.advance_booking_days,
        no_show_grace_period_minutes=request.no_show_grace_period_minutes,
        max_reschedules=request.max_reschedules,
        is_active=True,
        created_by=changed_by,
    )
    db.add(new_policy)
    db.flush()

    db.add(
        AppointmentPolicyHistory(
            old_policy_id=old_policy.policy_id,
            new_policy_id=new_policy.policy_id,
            changed_by=changed_by,
            reason=request.reason,
        )
    )

    db.commit()
    db.refresh(new_policy)
    return new_policy


def _validate_policy_values(request: UpdateAppointmentPolicyRequest) -> None:
    if request.cancellation_window_hours <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cancellation_window_hours must be greater than 0")
    if request.reschedule_window_hours <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reschedule_window_hours must be greater than 0")
    if request.advance_booking_days <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="advance_booking_days must be greater than 0")
    if request.no_show_grace_period_minutes <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no_show_grace_period_minutes must be greater than 0")
    if request.max_reschedules <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="max_reschedules must be greater than 0")
