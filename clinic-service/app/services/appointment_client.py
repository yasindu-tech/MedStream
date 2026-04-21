from datetime import date
from typing import Optional
from uuid import UUID

import httpx
from fastapi import HTTPException, status

import logging
from app.config import settings

logger = logging.getLogger(__name__)



def get_clinic_future_appointments_count(clinic_id: UUID) -> int:
    url = f"{settings.APPOINTMENT_SERVICE_URL}/internal/clinics/{clinic_id}/pending-future-appointments"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Appointment service unavailable: {str(exc)}",
        )

    if response.status_code == status.HTTP_200_OK:
        try:
            data = response.json()
            return int(data.get("pending_future_appointments", 0))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Appointment service returned invalid JSON.",
            )

    if response.status_code == status.HTTP_404_NOT_FOUND:
        return 0

    detail = response.text
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Appointment service returned unexpected status: {response.status_code} - {detail}",
    )


def get_doctor_future_appointments_count(doctor_id: UUID, clinic_id: UUID) -> int:
    url = f"{settings.APPOINTMENT_SERVICE_URL}/internal/appointments/pending-future"
    params = {"doctor_id": str(doctor_id), "clinic_id": str(clinic_id)}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
    except httpx.RequestError as exc:
        logger.error(f"Request error calling appointment service: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Appointment service unavailable: {str(exc)}",
        )

    if response.status_code == status.HTTP_200_OK:
        try:
            data = response.json()
            return int(data.get("pending_future_appointments", 0))
        except ValueError:
            logger.error(f"Appointment service returned invalid JSON: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Appointment service returned invalid JSON.",
            )

    if response.status_code == status.HTTP_404_NOT_FOUND:
        return 0

    detail = response.text
    logger.error(f"Appointment service returned {response.status_code}: {detail}")
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Appointment service returned unexpected status: {response.status_code} - {detail}",
    )



def get_clinic_operational_dashboard(clinic_id: UUID) -> dict:
    url = f"{settings.APPOINTMENT_SERVICE_URL}/internal/clinics/{clinic_id}/dashboard"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Appointment service unavailable: {str(exc)}",
        )

    if response.status_code == status.HTTP_200_OK:
        try:
            return response.json()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Appointment service returned invalid JSON.",
            )

    detail = response.text
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Appointment service returned unexpected status: {response.status_code} - {detail}",
    )


def get_clinic_appointments(
    clinic_id: UUID,
    page: int = 1,
    size: int = 20,
    target_date: date | None = None,
    status_filter: str | None = None,
    consultation_type: str | None = None,
) -> dict:
    url = f"{settings.APPOINTMENT_SERVICE_URL}/internal/clinics/{clinic_id}/appointments"
    params: dict[str, str | int] = {"page": page, "size": size}
    if target_date:
        params["date"] = target_date.isoformat()
    if status_filter:
        params["status"] = status_filter
    if consultation_type:
        params["consultation_type"] = consultation_type

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Appointment service unavailable: {str(exc)}",
        )

    if response.status_code == status.HTTP_200_OK:
        try:
            return response.json()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Appointment service returned invalid JSON.",
            )

    detail = response.text
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Appointment service returned unexpected status: {response.status_code} - {detail}",
    )


def get_platform_active_patients_count() -> int:
    url = f"{settings.APPOINTMENT_SERVICE_URL}/internal/platform/active-patients"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Appointment service unavailable: {str(exc)}",
        )

    if response.status_code == status.HTTP_200_OK:
        try:
            data = response.json()
            return int(data.get("active_patients", 0))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Appointment service returned invalid JSON.",
            )

    detail = response.text
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Appointment service returned unexpected status: {response.status_code} - {detail}",
    )


def get_platform_daily_bookings_count(target_date: str | None = None) -> int:
    url = f"{settings.APPOINTMENT_SERVICE_URL}/internal/platform/daily-bookings"
    params = {}
    if target_date:
        params["date"] = target_date

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Appointment service unavailable: {str(exc)}",
        )

    if response.status_code == status.HTTP_200_OK:
        try:
            data = response.json()
            return int(data.get("daily_bookings", 0))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Appointment service returned invalid JSON.",
            )

    detail = response.text
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Appointment service returned unexpected status: {response.status_code} - {detail}",
    )
