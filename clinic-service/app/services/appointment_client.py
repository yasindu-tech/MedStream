from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.config import settings


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
