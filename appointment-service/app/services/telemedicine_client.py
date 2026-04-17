"""Internal HTTP client for telemedicine-service orchestration."""
from __future__ import annotations

from datetime import date
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.config import settings


def provision_session_for_appointment(appointment_id: UUID, consultation_type: str) -> dict:
    payload = {
        "appointment_id": str(appointment_id),
        "consultation_type": consultation_type,
    }
    return _post("/internal/sessions/provision", payload)


def invalidate_session_for_appointment(appointment_id: UUID, reason: str | None = None) -> dict:
    payload = {
        "appointment_id": str(appointment_id),
        "reason": reason,
    }
    return _post("/internal/sessions/invalidate", payload)


def reschedule_session_for_appointment(
    appointment_id: UUID,
    *,
    new_date: date,
    new_start_time: str,
    reason: str | None = None,
) -> dict:
    payload = {
        "appointment_id": str(appointment_id),
        "new_date": new_date.isoformat(),
        "new_start_time": new_start_time,
        "reason": reason,
    }
    return _post("/internal/sessions/reschedule", payload)


def _post(path: str, payload: dict) -> dict:
    url = f"{settings.TELEMEDICINE_SERVICE_URL}{path}"
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text or f"Telemedicine service error ({exc.response.status_code})."
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemedicine service is unavailable.",
        )
