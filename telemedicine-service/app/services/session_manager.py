"""Business logic for telemedicine session lifecycle."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import cast
from uuid import UUID

from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Appointment, TelemedicineSession, TelemedicineSessionEvent
from app.schemas import JoinTokenPayload
from app.services.google_meet_client import create_google_meet_link


ALLOWED_CONSULTATION_TYPES = {"telemedicine", "virtual"}
SESSION_ACTIVE_STATES = {"scheduled", "rescheduled"}
logger = logging.getLogger(__name__)


def provision_session_for_appointment(
    db: Session,
    *,
    appointment_id: UUID,
    consultation_type: str,
) -> tuple[TelemedicineSession, bool]:
    if consultation_type.lower() not in ALLOWED_CONSULTATION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telemedicine session can only be provisioned for telemedicine appointments.",
        )

    existing = (
        db.query(TelemedicineSession)
        .filter(TelemedicineSession.appointment_id == appointment_id)
        .first()
    )
    if existing:
        return existing, False

    appointment = _get_appointment(db, appointment_id)
    provider_name, meeting_link = _generate_provider_link(db, appointment)

    session = TelemedicineSession(
        appointment_id=appointment_id,
        provider_name=provider_name,
        meeting_link=meeting_link,
        status="scheduled",
        session_version=1,
        token_version=1,
    )
    db.add(session)
    db.flush()

    _record_event(
        db,
        session_id=cast(UUID, session.session_id),
        event_type="session_provisioned",
        actor="system",
        details="Session created for telemedicine appointment.",
    )

    db.commit()
    db.refresh(session)
    return session, True


def generate_join_link(
    db: Session,
    *,
    appointment_id: UUID,
    participant_role: str,
    participant_user_id: UUID,
) -> tuple[TelemedicineSession, str, int]:
    session = _get_session_by_appointment(db, appointment_id)

    if session.status not in SESSION_ACTIVE_STATES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session is not active for joining (status={session.status}).",
        )

    expires_in_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)

    payload = {
        "sub": str(participant_user_id),
        "participant_role": participant_role,
        "session_id": str(session.session_id),
        "appointment_id": str(session.appointment_id),
        "token_version": session.token_version,
        "session_version": session.session_version,
        "type": "telemedicine_join",
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    join_url = f"{session.meeting_link}?token={token}"

    _record_event(
        db,
        session_id=cast(UUID, session.session_id),
        event_type="join_link_generated",
        actor=str(participant_user_id),
        details=f"role={participant_role}",
    )
    db.commit()

    return session, join_url, expires_in_seconds


def invalidate_session(
    db: Session,
    *,
    appointment_id: UUID,
    reason: str | None,
) -> TelemedicineSession:
    session = _get_session_by_appointment(db, appointment_id)

    current_token_version = int(cast(int, session.token_version))
    setattr(session, "status", "invalidated")
    setattr(session, "token_version", current_token_version + 1)

    _record_event(
        db,
        session_id=cast(UUID, session.session_id),
        event_type="session_invalidated",
        actor="system",
        details=reason or "Session invalidated.",
    )

    db.commit()
    db.refresh(session)
    return session


def reschedule_session(
    db: Session,
    *,
    appointment_id: UUID,
    new_date: date | None = None,
    new_start_time: str | None = None,
    reason: str | None,
) -> TelemedicineSession:
    session = _get_session_by_appointment(db, appointment_id)
    appointment = _get_appointment(db, appointment_id)

    current_session_version = int(cast(int, session.session_version))
    current_token_version = int(cast(int, session.token_version))
    setattr(session, "status", "rescheduled")
    setattr(session, "session_version", current_session_version + 1)
    setattr(session, "token_version", current_token_version + 1)

    provider_name, meeting_link = _generate_provider_link(db, appointment)
    setattr(session, "provider_name", provider_name)
    setattr(session, "meeting_link", meeting_link)

    _record_event(
        db,
        session_id=cast(UUID, session.session_id),
        event_type="session_rescheduled",
        actor="system",
        details=reason or "Session regenerated after appointment reschedule.",
    )

    db.commit()
    db.refresh(session)
    return session


def verify_join_token(db: Session, *, token: str) -> JoinTokenPayload:
    try:
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired join token.",
        ) from exc

    if decoded.get("type") != "telemedicine_join":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
        )

    payload = JoinTokenPayload(
        session_id=UUID(decoded["session_id"]),
        appointment_id=UUID(decoded["appointment_id"]),
        participant_role=decoded["participant_role"],
        participant_user_id=UUID(decoded["sub"]),
        token_version=int(decoded["token_version"]),
        session_version=int(decoded["session_version"]),
    )

    session = db.query(TelemedicineSession).filter(TelemedicineSession.session_id == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    session_token_version = int(cast(int, session.token_version))
    session_version = int(cast(int, session.session_version))
    if session_token_version != payload.token_version or session_version != payload.session_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Join token is no longer valid.",
        )

    if session.status not in SESSION_ACTIVE_STATES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session is not active (status={session.status}).",
        )

    return payload


def _get_session_by_appointment(db: Session, appointment_id: UUID) -> TelemedicineSession:
    session = (
        db.query(TelemedicineSession)
        .filter(TelemedicineSession.appointment_id == appointment_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telemedicine session not found.")
    return session


def _get_appointment(db: Session, appointment_id: UUID) -> Appointment:
    appointment = db.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    return appointment


def _generate_provider_link(db: Session, appointment: Appointment) -> tuple[str, str]:
    provider = settings.TELEMEDICINE_PROVIDER.strip().lower()
    if provider == "google":
        try:
            return (
                "Google Meet",
                create_google_meet_link(db, appointment_id=cast(UUID, appointment.appointment_id)),
            )
        except Exception as exc:
            # Fail-open: preserve booking flow even if provider integration is unavailable.
            logger.warning("Google Meet generation failed for appointment %s: %s", appointment.appointment_id, exc)

    base = settings.MEETING_LINK_BASE_URL.rstrip("/")
    return settings.TELEMEDICINE_PROVIDER_NAME, f"{base}/{appointment.appointment_id}"


def _record_event(
    db: Session,
    *,
    session_id: UUID,
    event_type: str,
    actor: str | None,
    details: str | None,
) -> None:
    db.add(
        TelemedicineSessionEvent(
            session_id=session_id,
            event_type=event_type,
            actor=actor,
            details=details,
        )
    )
