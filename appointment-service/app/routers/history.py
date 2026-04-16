"""Public history router."""
from __future__ import annotations
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import AppointmentListPaginatedResponse
from app.services.history import fetch_appointment_history


router = APIRouter(tags=["Appointment History"])

@router.get("/appointments", response_model=AppointmentListPaginatedResponse, status_code=200)
def view_appointment_history_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    date: Optional[date] = Query(None, description="Filter by exact date"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. cancelled, scheduled)"),
    consultation_type: Optional[str] = Query(None, description="Filter by physical or telemedicine"),
    user: dict = Depends(require_roles("patient", "doctor", "clinic_admin", "system_admin")),
    db: Session = Depends(get_db),
) -> AppointmentListPaginatedResponse:
    """
    Unified router resolving appointment logs securely mapping parameters directly into Role-based DB configurations natively!
    """
    return fetch_appointment_history(
        db,
        user=user,
        page=page,
        size=size,
        filter_date=date,
        filter_status=status,
        filter_type=consultation_type,
    )
