"""HTTP client for fetching booked slots from the Appointment Service."""
from __future__ import annotations
from typing import Dict, List, Tuple
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
    except (httpx.RequestError, httpx.HTTPStatusError, KeyError, ValueError):
        # Fail-open: if appointment-service is unreachable or returns
        # unexpected data, return no booked slots so search still works.
        return []


def get_booked_slots_batch(
    doctor_ids: List[str],
    target_date: date,
) -> Dict[Tuple[str, str], List[BookedSlot]]:
    """
    Batch-fetch booked slots for multiple doctors on a given date.
    Returns a dict keyed by (doctor_id, clinic_id) → list of BookedSlot.

    This avoids N+1 HTTP calls when computing available slots for many doctors.
    """
    if not doctor_ids:
        return {}

    url = f"{settings.APPOINTMENT_SERVICE_URL}/internal/appointments/booked-slots/batch"
    params = {
        "doctor_ids": ",".join(doctor_ids),
        "date": target_date.isoformat(),
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        result: Dict[Tuple[str, str], List[BookedSlot]] = {}
        for item in data:
            key = (item["doctor_id"], item["clinic_id"])
            result.setdefault(key, []).append(
                BookedSlot(item["start_time"], item["end_time"])
            )
        return result
    except (httpx.RequestError, httpx.HTTPStatusError, KeyError, ValueError):
        return {}


def get_effective_policy() -> dict:
    """
    Fetch effective appointment policy from appointment-service.

    Fail-open to conservative defaults when unavailable.
    """
    url = f"{settings.APPOINTMENT_SERVICE_URL}/internal/policies/effective"
    defaults = {
        "advance_booking_days": 14,
    }
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
            return {
                "advance_booking_days": int(data.get("advance_booking_days", defaults["advance_booking_days"])),
            }
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError, TypeError):
        return defaults
