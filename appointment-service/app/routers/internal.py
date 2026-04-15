"""Internal router — service-to-service calls only (no JWT needed).

Provides booked slot data to doctor-service for slot computation.
Not exposed through the nginx gateway.
"""
from __future__ import annotations
from datetime import date
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment
from app.schemas import BookedSlotResponse

router = APIRouter(tags=["internal"])

# Statuses that occupy a slot (cancelled/completed do NOT block)
OCCUPIED_STATUSES = {"scheduled", "confirmed", "in_progress"}


@router.get("/appointments/booked-slots", response_model=List[BookedSlotResponse])
def get_booked_slots(
    doctor_id: UUID = Query(..., description="Doctor UUID"),
    clinic_id: UUID = Query(..., description="Clinic UUID"),
    date: date = Query(..., description="Target date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> List[BookedSlotResponse]:
    """
    Return all occupied appointments for a given doctor + clinic + date.
    Consumed by doctor-service to compute available slots.
    """
    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.clinic_id == clinic_id,
            Appointment.appointment_date == date,
            Appointment.status.in_(OCCUPIED_STATUSES),
        )
        .all()
    )

    return [
        BookedSlotResponse(
            doctor_id=appt.doctor_id,
            clinic_id=appt.clinic_id,
            date=appt.appointment_date,
            start_time=appt.start_time.strftime("%H:%M"),
            end_time=appt.end_time.strftime("%H:%M"),
        )
        for appt in appointments
    ]


@router.get("/appointments/booked-slots/batch", response_model=List[BookedSlotResponse])
def get_booked_slots_batch(
    doctor_ids: str = Query(..., description="Comma-separated doctor UUIDs"),
    date: date = Query(..., description="Target date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> List[BookedSlotResponse]:
    """
    Return all occupied appointments for multiple doctors on a given date.
    Batch endpoint to avoid N+1 HTTP calls from doctor-service.
    """
    parsed_ids = [UUID(d.strip()) for d in doctor_ids.split(",") if d.strip()]
    if not parsed_ids:
        return []

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id.in_(parsed_ids),
            Appointment.appointment_date == date,
            Appointment.status.in_(OCCUPIED_STATUSES),
        )
        .all()
    )

    return [
        BookedSlotResponse(
            doctor_id=appt.doctor_id,
            clinic_id=appt.clinic_id,
            date=appt.appointment_date,
            start_time=appt.start_time.strftime("%H:%M"),
            end_time=appt.end_time.strftime("%H:%M"),
        )
        for appt in appointments
    ]
