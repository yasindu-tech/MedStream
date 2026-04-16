"""Outcome endpoints for appointment completion/no-show/arrival updates."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import AppointmentOutcomeResponse, MarkArrivedRequest
from app.services.outcome import mark_arrived, mark_completed

router = APIRouter(tags=["Appointment Outcomes"])


@router.post("/appointments/{appointment_id}/arrived", response_model=AppointmentOutcomeResponse)
def mark_arrived_endpoint(
    request: MarkArrivedRequest,
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("doctor", "staff", "admin")),
    db: Session = Depends(get_db),
) -> AppointmentOutcomeResponse:
    appt = mark_arrived(
        db,
        appointment_id=appointment_id,
        actor_role=user["role"],
        actor_user_id=user["sub"],
        reason=request.reason,
    )
    return AppointmentOutcomeResponse(
        appointment_id=appt.appointment_id,
        status=appt.status,
        changed_at=datetime.now().isoformat(),
        message="Appointment marked as arrived",
    )


@router.post("/appointments/{appointment_id}/complete", response_model=AppointmentOutcomeResponse)
def mark_completed_endpoint(
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("doctor", "staff", "admin")),
    db: Session = Depends(get_db),
) -> AppointmentOutcomeResponse:
    appt = mark_completed(
        db,
        appointment_id=appointment_id,
        actor_role=user["role"],
        actor_user_id=user["sub"],
    )
    return AppointmentOutcomeResponse(
        appointment_id=appt.appointment_id,
        status=appt.status,
        changed_at=(appt.completed_at or datetime.now()).isoformat(),
        message="Appointment marked as completed",
    )
