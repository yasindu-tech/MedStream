"""HTTP client for fetching booked slots from the Appointment Service."""
from __future__ import annotations
from typing import List
from datetime import date

import httpx
from app.config import settings


class BookedSlot:
    def __init__(self, start_time: str, end_time: str):
        self.start_time = start_time
        self.end_time = end_time


def get_booked_slots(doctor_id: str, clinic_id: str, target_date: date) -> List[BookedSlot]:
    """
    Call appointment-service:/internal/appointments/booked-slots and return
    a list of (start_time, end_time) pairs that are already taken.

    Returns an empty list if the service is unreachable (fail-open so search
    still works even if appointment-service is temporarily down — worst case
    a slot appears bookable and gets rejected at booking time).
    """
    url = f"{settings.APPOINTMENT_SERVICE_URL}/internal/appointments/booked-slots"
    params = {
        "doctor_id": str(doctor_id),
        "clinic_id": str(clinic_id),
        "date": target_date.isoformat(),
    }
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return [BookedSlot(item["start_time"], item["end_time"]) for item in data]
    except Exception:
        # Fail-open: if appointment-service is unreachable, return no booked slots
        return []
