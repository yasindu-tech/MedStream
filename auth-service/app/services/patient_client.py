from __future__ import annotations

import httpx
from fastapi import HTTPException, status

from app.config import settings


def create_patient_profile(payload: dict) -> dict:
    url = f"{settings.PATIENT_SERVICE_URL}/internal/patients"
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT):
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=exc.response.text or f"Patient service returned status {exc.response.status_code}",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Patient service returned status {exc.response.status_code}",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Patient service unavailable. Please try again later.",
        )
