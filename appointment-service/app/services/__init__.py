"""HTTP client for calling doctor-service internally from appointment-service."""
from __future__ import annotations
from datetime import date
from typing import Optional
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.config import settings


def search_doctors(
    *,
    specialty: Optional[str] = None,
    target_date: Optional[date] = None,
    consultation_type: Optional[str] = None,
    clinic_id: Optional[UUID] = None,
) -> dict:
    """
    Forward the patient's search request to doctor-service and return
    the raw parsed JSON response body.
    """
    params: dict = {}
    if specialty:
        params["specialty"] = specialty
    if target_date:
        params["date"] = target_date.isoformat()
    if consultation_type:
        params["consultation_type"] = consultation_type
    if clinic_id:
        params["clinic_id"] = str(clinic_id)

    url = f"{settings.DOCTOR_SERVICE_URL}/internal/doctors/search"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Doctor service returned an error: {exc.response.status_code}",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Doctor service is currently unavailable. Please try again later.",
        )
