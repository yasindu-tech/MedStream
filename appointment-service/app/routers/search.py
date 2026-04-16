"""Public doctor endpoints — patient-facing.

Accessible via the API gateway at:
  GET /appointments/doctors/search           (AS-01)
  GET /appointments/doctors/{id}/profile     (AS-02)

Requires a valid JWT with role = patient, clinic_admin, or super_admin.
Proxies requests to doctor-service internally and returns the results.
"""
from __future__ import annotations
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.middleware import require_roles
from app.schemas import DoctorSearchResponse, DoctorProfileResponse
from app.services import search_doctors, get_doctor_profile

router = APIRouter(tags=["Doctor Search & Profile"])


# ---------------------------------------------------------------------------
# AS-01: Search doctors
# ---------------------------------------------------------------------------

@router.get("/doctors/search", response_model=DoctorSearchResponse)
def doctor_search(
    specialty: Optional[str] = Query(None, description="Filter by specialization (partial match, e.g. 'Cardiology')"),
    date: Optional[date] = Query(None, description="Availability date (YYYY-MM-DD)"),
    consultation_type: Optional[str] = Query(None, description="'physical' or 'telemedicine'"),
    clinic_id: Optional[UUID] = Query(None, description="Filter by specific clinic UUID"),
    _user: dict = Depends(require_roles("patient", "clinic_admin", "super_admin")),
) -> DoctorSearchResponse:
    """
    Search for available doctors.

    All filters are optional. When `date` is provided, results include
    computed available time slots with booked slots excluded.

    Returns an empty result set (never 404) when no doctors are found.
    Results are sorted by earliest available slot; no-slot doctors appear last.
    """
    data = search_doctors(
        specialty=specialty,
        target_date=date,
        consultation_type=consultation_type,
        clinic_id=clinic_id,
    )
    return DoctorSearchResponse(**data)


# ---------------------------------------------------------------------------
# AS-02: Doctor profile
# ---------------------------------------------------------------------------

@router.get("/doctors/{doctor_id}/profile", response_model=DoctorProfileResponse)
def doctor_profile(
    doctor_id: UUID,
    date: Optional[date] = Query(None, description="Target date for slot availability (YYYY-MM-DD)"),
    _user: dict = Depends(require_roles("patient", "clinic_admin", "super_admin")),
) -> DoctorProfileResponse:
    """
    View a doctor's full profile and available time slots.

    Returns 404 if the doctor is not found, inactive, or unverified.
    When `date` is provided, available slots are computed for that day
    (excluding booked slots and respecting the advance booking window).
    """
    data = get_doctor_profile(doctor_id=doctor_id, target_date=date)
    return DoctorProfileResponse(**data)
