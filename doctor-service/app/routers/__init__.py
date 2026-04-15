"""Internal router — not exposed through the nginx gateway.

All routes under /internal/* are for service-to-service calls only.
No JWT auth is applied here; network-level isolation is the security boundary.
"""
from __future__ import annotations
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import DoctorSearchResponse
from app.services.doctor_search import search_doctors

router = APIRouter(tags=["internal"])


@router.get("/doctors/search", response_model=DoctorSearchResponse)
def internal_doctor_search(
    specialty: Optional[str] = Query(None, description="Filter by specialization (partial match)"),
    date: Optional[date] = Query(None, description="Target date for slot availability (YYYY-MM-DD)"),
    consultation_type: Optional[str] = Query(None, description="'physical' or 'telemedicine'"),
    clinic_id: Optional[UUID] = Query(None, description="Restrict to a specific clinic"),
    db: Session = Depends(get_db),
) -> DoctorSearchResponse:
    """
    Internal endpoint consumed by patient-service.
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
