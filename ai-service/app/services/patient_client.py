from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.config import settings


def get_patient_medical_summary(*, patient_id: UUID) -> dict:
    url = f"{settings.PATIENT_SERVICE_URL}/internal/patients/{patient_id}/medical-summary"
    headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    try:
        with httpx.Client(timeout=settings.OVERVIEW_HTTP_TIMEOUT_SECONDS) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Patient service returned an error: {exc.response.status_code}",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Patient service is currently unavailable.",
        )
