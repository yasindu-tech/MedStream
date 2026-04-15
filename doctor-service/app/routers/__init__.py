"""Internal router — not exposed through the nginx gateway.

All routes under /internal/* are for service-to-service calls only.
No JWT auth is applied here; network-level isolation is the security boundary.
"""
from __future__ import annotations
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Doctor
from app.schemas import DoctorSearchResponse, DoctorProfileResponse, SlotValidationResponse, DoctorIdResponse
from app.services.doctor_search import search_doctors
from app.services.doctor_profile import get_doctor_profile
from app.services.slot_validator import validate_slot

router = APIRouter(tags=["internal"])


# ---------------------------------------------------------------------------
# AS-01: Doctor search
# ---------------------------------------------------------------------------

@router.get("/doctors/search", response_model=DoctorSearchResponse)
def internal_doctor_search(
    specialty: Optional[str] = Query(None, description="Filter by specialization (partial match)"),
    date: Optional[date] = Query(None, description="Target date for slot availability (YYYY-MM-DD)"),
    consultation_type: Optional[str] = Query(None, description="'physical' or 'telemedicine'"),
    clinic_id: Optional[UUID] = Query(None, description="Restrict to a specific clinic"),
    db: Session = Depends(get_db),
) -> DoctorSearchResponse:
    """
    Internal endpoint consumed by appointment-service.
    Returns matching doctors with available time slots.

    - Returns 200 with [] when no doctors match — never 404.
    - Doctors with no available slots are included with has_slots=false.
    - Sorted by earliest available slot; no-slot doctors are last.
    """
    results = search_doctors(
        db,
        specialty=specialty,
        target_date=date,
        consultation_type=consultation_type,
        clinic_id=clinic_id,
    )
    return DoctorSearchResponse(
        results=results,
        total=len(results),
        empty_state=len(results) == 0,
    )


# ---------------------------------------------------------------------------
# AS-02: Doctor profile
# ---------------------------------------------------------------------------

@router.get("/doctors/{doctor_id}/profile", response_model=DoctorProfileResponse)
def internal_doctor_profile(
    doctor_id: UUID,
    date: Optional[date] = Query(None, description="Target date for slot availability (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> DoctorProfileResponse:
    """
    Internal endpoint consumed by appointment-service.
    Returns full doctor profile with clinic details and availability.

    Returns 404 if doctor is not found, inactive, or unverified.
    """
    profile = get_doctor_profile(db, doctor_id, target_date=date)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Doctor not found, inactive, or unverified",
        )
    return profile


# ---------------------------------------------------------------------------
# AS-03: Slot validation
# ---------------------------------------------------------------------------

@router.get("/doctors/{doctor_id}/validate-slot", response_model=SlotValidationResponse)
def internal_validate_slot(
    doctor_id: UUID,
    clinic_id: UUID = Query(..., description="Clinic UUID"),
    date: date = Query(..., description="Target date (YYYY-MM-DD)"),
    start_time: str = Query(..., description="Slot start time (HH:MM)"),
    consultation_type: str = Query(..., description="'physical' or 'telemedicine'"),
    db: Session = Depends(get_db),
) -> SlotValidationResponse:
    """
    Lightweight slot validation for the booking flow.
    Confirms doctor/clinic/day/time/consultation_type are all valid and bookable.
    """
    result = validate_slot(
        db,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
        target_date=date,
        start_time=start_time,
        consultation_type=consultation_type,
    )
    return SlotValidationResponse(**result)


# ---------------------------------------------------------------------------
# AS-04: Resolve user_id to doctor_id
# ---------------------------------------------------------------------------

@router.get("/doctors/by-user/{user_id}", response_model=DoctorIdResponse)
def internal_doctor_by_user(
    user_id: str,
    db: Session = Depends(get_db),
) -> DoctorIdResponse:
    """
    Internal endpoint to resolve an auth user_id to an admin DB doctor_id.
    """
    doctor = db.query(Doctor).filter(Doctor.user_id == UUID(user_id)).first()
    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor profile not found for this user",
        )

    return DoctorIdResponse(
        doctor_id=doctor.doctor_id,
        full_name=doctor.full_name,
    )

