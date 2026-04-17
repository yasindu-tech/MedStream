"""Public telemedicine session endpoints."""
from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware import require_roles
from app.models import Appointment, Patient, TelemedicineSession
from app.schemas import JoinLinkRequest, JoinLinkResponse, TelemedicineSessionSummary
from app.services.session_manager import generate_join_link, verify_join_token

router = APIRouter(tags=["telemedicine-sessions"])


@router.post("/sessions/join-link", response_model=JoinLinkResponse)
def create_join_link(
    request: JoinLinkRequest,
    user: dict = Depends(require_roles("patient", "doctor", "staff", "admin")),
    db: Session = Depends(get_db),
) -> JoinLinkResponse:
    user_sub = user.get("sub")
    user_role = user.get("role")
    if not user_sub or not user_role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject or role claim.",
        )

    try:
        participant_user_id = UUID(user_sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject claim is not a valid UUID.",
        ) from exc

    _enforce_participant_scope(
        db,
        appointment_id=request.appointment_id,
        participant_user_id=participant_user_id,
        participant_role=user_role,
    )

    session, join_url, expires_in_seconds = generate_join_link(
        db,
        appointment_id=request.appointment_id,
        participant_role=user_role,
        participant_user_id=participant_user_id,
    )
    return JoinLinkResponse(
        session_id=session.session_id,
        join_url=join_url,
        expires_in_seconds=expires_in_seconds,
    )


@router.get("/sessions/validate", response_model=TelemedicineSessionSummary)
def validate_join_token(
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
) -> TelemedicineSessionSummary:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be a Bearer token.",
        )

    token = authorization.removeprefix("Bearer ").strip()
    payload = verify_join_token(db, token=token)
    session = db.query(TelemedicineSession).filter(TelemedicineSession.session_id == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    return TelemedicineSessionSummary(
        session_id=payload.session_id,
        appointment_id=payload.appointment_id,
        status=session.status,
        provider_name=session.provider_name,
        session_version=payload.session_version,
        token_version=payload.token_version,
    )


def _enforce_participant_scope(
    db: Session,
    *,
    appointment_id: UUID,
    participant_user_id: UUID,
    participant_role: str,
) -> None:
    appointment = db.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")

    if participant_role == "patient":
        patient = db.query(Patient).filter(Patient.patient_id == appointment.patient_id).first()
        if not patient or patient.user_id != participant_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Patient is not authorized for this telemedicine session.",
            )
        return

    if participant_role == "doctor":
        doctor_id = _resolve_doctor_id_by_user(participant_user_id)
        if appointment.doctor_id != doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctor is not authorized for this telemedicine session.",
            )
        return

    # Staff/admin are allowed to generate operational support links.


def _resolve_doctor_id_by_user(user_id: UUID) -> UUID:
    url = f"{settings.DOCTOR_SERVICE_URL}/internal/doctors/by-user/{user_id}"
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
            return UUID(payload["doctor_id"])
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify doctor identity for telemedicine session.",
        ) from exc
