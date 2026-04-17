"""Internal telemedicine callbacks for appointment no-show automation."""
from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.schemas import (
    AttendanceUpdateRequest,
    InvalidateSessionRequest,
    ProvisionSessionRequest,
    ProvisionSessionResponse,
    RescheduleSessionRequest,
    TelemedicineSessionSummary,
)
from app.services.session_manager import (
    invalidate_session,
    provision_session_for_appointment,
    reschedule_session,
)

router = APIRouter(tags=["internal"])

@router.post("/appointments/{appointment_id}/attendance")
def report_attendance(appointment_id: UUID, request: AttendanceUpdateRequest) -> dict:
    appointment_service_url = settings.APPOINTMENT_SERVICE_URL

    if request.joined_within_grace:
        endpoint = f"{appointment_service_url}/internal/appointments/{appointment_id}/mark-arrived"
        payload = {"reason": request.reason or "Patient joined telemedicine session within grace period"}
    else:
        endpoint = f"{appointment_service_url}/internal/appointments/{appointment_id}/mark-no-show"
        payload = {
            "reason": request.reason or "Patient did not join telemedicine session within grace period",
            "mark_by": "system",
            "observed_join_within_grace": False,
        }

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            return {
                "appointment_id": str(appointment_id),
                "forwarded": True,
                "result": response.json(),
            }
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to update appointment outcome from telemedicine workflow: {exc}",
        )


@router.post("/sessions/provision", response_model=ProvisionSessionResponse)
def provision_session(
    request: ProvisionSessionRequest,
    db: Session = Depends(get_db),
) -> ProvisionSessionResponse:
    session, created = provision_session_for_appointment(
        db,
        appointment_id=request.appointment_id,
        consultation_type=request.consultation_type,
    )
    return ProvisionSessionResponse(
        session_id=session.session_id,
        appointment_id=session.appointment_id,
        provider_name=session.provider_name,
        status=session.status,
        session_version=session.session_version,
        token_version=session.token_version,
        created=created,
    )


@router.post("/sessions/invalidate", response_model=TelemedicineSessionSummary)
def invalidate_session_for_appointment(
    request: InvalidateSessionRequest,
    db: Session = Depends(get_db),
) -> TelemedicineSessionSummary:
    session = invalidate_session(
        db,
        appointment_id=request.appointment_id,
        reason=request.reason,
    )
    return TelemedicineSessionSummary(
        session_id=session.session_id,
        appointment_id=session.appointment_id,
        status=session.status,
        provider_name=session.provider_name,
        session_version=session.session_version,
        token_version=session.token_version,
    )


@router.post("/sessions/reschedule", response_model=TelemedicineSessionSummary)
def reschedule_session_for_appointment(
    request: RescheduleSessionRequest,
    db: Session = Depends(get_db),
) -> TelemedicineSessionSummary:
    session = reschedule_session(
        db,
        appointment_id=request.appointment_id,
        new_date=request.new_date,
        new_start_time=request.new_start_time,
        reason=request.reason,
    )
    return TelemedicineSessionSummary(
        session_id=session.session_id,
        appointment_id=session.appointment_id,
        status=session.status,
        provider_name=session.provider_name,
        session_version=session.session_version,
        token_version=session.token_version,
    )
