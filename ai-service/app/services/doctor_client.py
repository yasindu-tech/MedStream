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
    headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params, headers=headers)
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


def get_doctor_profile(
    doctor_id: UUID,
    target_date: Optional[date] = None,
) -> dict:
    params: dict = {}
    if target_date:
        params["date"] = target_date.isoformat()

    url = f"{settings.DOCTOR_SERVICE_URL}/internal/doctors/{doctor_id}/profile"
    headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params, headers=headers)
            if response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Doctor not found, inactive, or unverified",
                )
            response.raise_for_status()
            return response.json()
    except HTTPException:
        raise
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
