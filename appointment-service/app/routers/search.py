"""Public doctor search router — patient-facing.

Accessible via the API gateway at:
  GET /appointments/doctors/search

Requires a valid JWT with role = patient (or admin).
Proxies the request to doctor-service internally and returns the results.
"""
from __future__ import annotations
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.middleware import require_roles
from app.schemas import DoctorSearchResponse
from app.services import search_doctors

router = APIRouter(tags=["Doctor Search"])


@router.get("/doctors/search", response_model=DoctorSearchResponse)
def doctor_search(
    specialty: Optional[str] = Query(None, description="Filter by specialization (partial match, e.g. 'Cardiology')"),
    date: Optional[date] = Query(None, description="Availability date (YYYY-MM-DD)"),
    consultation_type: Optional[str] = Query(None, description="'physical' or 'telemedicine'"),
    clinic_id: Optional[UUID] = Query(None, description="Filter by specific clinic UUID"),
    _user: dict = Depends(require_roles("patient", "admin")),
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
