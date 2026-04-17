import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _http_get(url: str) -> dict:
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        logger.warning("Appointment service request failed: %s", exc)
        raise


def get_patient_pending_future_appointments(user_id: str) -> int:
    url = f"{settings.APPOINTMENT_SERVICE_URL.rstrip('/')}/internal/appointments/pending-future/patient/user/{user_id}"
    payload = _http_get(url)
    return int(payload.get("pending_future_appointments", 0))


def get_doctor_pending_future_appointments(user_id: str) -> int:
    doctor_url = f"{settings.DOCTOR_SERVICE_URL.rstrip('/')}/internal/doctors/by-user/{user_id}"
    try:
        response = _http_get(doctor_url)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return 0
        raise

    doctor_id = response.get("doctor_id")
    if not doctor_id:
        return 0
    appointment_url = f"{settings.APPOINTMENT_SERVICE_URL.rstrip('/')}/internal/appointments/pending-future/doctor/{doctor_id}"
    payload = _http_get(appointment_url)
    return int(payload.get("pending_future_appointments", 0))
