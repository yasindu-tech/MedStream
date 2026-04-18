"""Internal client for saving generated consultation summaries in patient-service."""
from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.config import settings


def upsert_post_consultation_summary(*, patient_id: UUID, payload: dict) -> dict:
    url = f"{settings.PATIENT_SERVICE_URL}/internal/patients/{patient_id}/consultation-summaries"
    headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Patient service returned an error: {exc.response.status_code}",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Patient service is currently unavailable. Please try again later.",
        )
