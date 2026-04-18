from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.config import settings


def get_pre_consultation_context(*, appointment_id: UUID, doctor_user_id: str) -> dict:
    url = f"{settings.APPOINTMENT_SERVICE_URL}/internal/appointments/{appointment_id}/pre-consultation-context"
    headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
    payload = {
        "doctor_user_id": doctor_user_id,
        "recent_limit": settings.OVERVIEW_RECENT_LIMIT,
    }

    try:
        with httpx.Client(timeout=settings.OVERVIEW_HTTP_TIMEOUT_SECONDS) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {403, 404}:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Appointment service returned an error: {exc.response.status_code}",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Appointment service is currently unavailable.",
        )
