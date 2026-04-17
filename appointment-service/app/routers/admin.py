"""Admin and clinic-staff appointment oversight endpoints."""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import (
    AppointmentListPaginatedResponse,
    AppointmentOutcomeResponse,
    AppointmentStatsResponse,
    AppointmentStatusHistoryItem,
    CancelAppointmentRequest,
    MarkNoShowRequest,
    TelemedicineLiveStatusPaginatedResponse,
)
from app.services.admin import get_appointment_stats, get_live_telemedicine_statuses, get_status_history_for_admin, list_appointments_for_admin
from app.services.cancellation import cancel_appointment
from app.services.outcome import mark_no_show

router = APIRouter(prefix="/admin", tags=["Appointment Admin"])


@router.get("/appointments", response_model=AppointmentListPaginatedResponse)
def admin_list_appointments(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    patient_id: Optional[UUID] = Query(None),
    doctor_id: Optional[UUID] = Query(None),
    clinic_id: Optional[UUID] = Query(None),
    patient_name: Optional[str] = Query(None),
    doctor_name: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    user: dict = Depends(require_roles("admin", "staff")),
    db: Session = Depends(get_db),
) -> AppointmentListPaginatedResponse:
    return list_appointments_for_admin(
        db,
        user=user,
        page=page,
        size=size,
        patient_id=patient_id,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
        patient_name=patient_name,
        doctor_name=doctor_name,
        date_from=date_from,
        date_to=date_to,
        status=status,
    )


@router.post("/appointments/{appointment_id}/cancel")
def admin_cancel_appointment(
    request: CancelAppointmentRequest,
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("admin", "staff")),
    db: Session = Depends(get_db),
) -> dict:
    return cancel_appointment(db, user=user, appointment_id=appointment_id, request=request)


@router.post("/appointments/{appointment_id}/no-show", response_model=AppointmentOutcomeResponse)
def admin_mark_no_show(
    request: MarkNoShowRequest,
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("admin", "staff")),
    db: Session = Depends(get_db),
) -> AppointmentOutcomeResponse:
    appt = mark_no_show(
        db,
        appointment_id=appointment_id,
        actor_role=user["role"],
        actor_user_id=user["sub"],
        reason=request.reason,
    )
    changed_at = appt.no_show_at.isoformat() if appt.no_show_at else date.today().isoformat()
    return AppointmentOutcomeResponse(
        appointment_id=appt.appointment_id,
        status=appt.status,
        changed_at=changed_at,
        message="Appointment marked as no-show",
    )


@router.get("/appointments/{appointment_id}/status-history", response_model=list[AppointmentStatusHistoryItem])
def admin_get_status_history(
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("admin", "staff")),
    db: Session = Depends(get_db),
) -> list[AppointmentStatusHistoryItem]:
    rows = get_status_history_for_admin(db, appointment_id=appointment_id, user=user)
    return [
        AppointmentStatusHistoryItem(
            history_id=row.history_id,
            old_status=row.old_status,
            new_status=row.new_status,
            changed_by=row.changed_by,
            reason=row.reason,
            changed_at=row.changed_at.isoformat() if row.changed_at else "",
        )
        for row in rows
    ]


@router.get("/statistics", response_model=AppointmentStatsResponse)
def admin_statistics(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    clinic_id: Optional[UUID] = Query(None),
    doctor_id: Optional[UUID] = Query(None),
    outcome: Optional[str] = Query(None),
    user: dict = Depends(require_roles("admin", "staff")),
    db: Session = Depends(get_db),
) -> AppointmentStatsResponse:
    return get_appointment_stats(
        db,
        user=user,
        date_from=date_from,
        date_to=date_to,
        clinic_id=clinic_id,
        doctor_id=doctor_id,
        outcome=outcome,
    )


@router.get("/telemedicine/live-statuses", response_model=TelemedicineLiveStatusPaginatedResponse)
def admin_live_telemedicine_statuses(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    clinic_id: Optional[UUID] = Query(None),
    doctor_id: Optional[UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    outcome: Optional[str] = Query(None),
    user: dict = Depends(require_roles("admin", "staff")),
    db: Session = Depends(get_db),
) -> TelemedicineLiveStatusPaginatedResponse:
    return get_live_telemedicine_statuses(
        db,
        user=user,
        page=page,
        size=size,
        clinic_id=clinic_id,
        doctor_id=doctor_id,
        date_from=date_from,
        date_to=date_to,
        outcome=outcome,
    )
