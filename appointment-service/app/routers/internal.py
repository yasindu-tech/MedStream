"""Internal router — service-to-service calls only (no JWT needed).

Provides booked slot data to doctor-service for slot computation.
Not exposed through the nginx gateway.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, Patient
from app.schemas import AppointmentOutcomeResponse, BookedSlotResponse, InternalNoShowRequest, MarkArrivedRequest
from app.services.outcome import mark_arrived, mark_no_show
from app.services.policy import resolve_effective_policy

router = APIRouter(tags=["internal"])

# Statuses that occupy a slot (cancelled/completed do NOT block)
OCCUPIED_STATUSES = {"scheduled", "confirmed", "pending_payment", "in_progress", "arrived"}


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
    try:
        parsed_ids = [UUID(d.strip()) for d in doctor_ids.split(",") if d.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid doctor_id format in query parameter")
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


@router.post("/appointments/{appointment_id}/mark-no-show", response_model=AppointmentOutcomeResponse)
def internal_mark_no_show(
    request: InternalNoShowRequest,
    appointment_id: UUID = Path(...),
    db: Session = Depends(get_db),
) -> AppointmentOutcomeResponse:
    appt = mark_no_show(
        db,
        appointment_id=appointment_id,
        actor_role=request.mark_by,
        actor_user_id="internal-system",
        reason=request.reason,
        observed_join_within_grace=request.observed_join_within_grace,
    )
    return AppointmentOutcomeResponse(
        appointment_id=appt.appointment_id,
        status=appt.status,
        changed_at=(appt.no_show_at or datetime.now()).isoformat(),
        message="Appointment marked as no-show",
    )


@router.post("/appointments/{appointment_id}/mark-arrived", response_model=AppointmentOutcomeResponse)
def internal_mark_arrived(
    request: MarkArrivedRequest,
    appointment_id: UUID = Path(...),
    db: Session = Depends(get_db),
) -> AppointmentOutcomeResponse:
    appt = mark_arrived(
        db,
        appointment_id=appointment_id,
        actor_role="system",
        actor_user_id="internal-system",
        reason=request.reason,
    )
    return AppointmentOutcomeResponse(
        appointment_id=appt.appointment_id,
        status=appt.status,
        changed_at=datetime.now().isoformat(),
        message="Appointment marked as arrived",
    )


@router.get("/clinics/{clinic_id}/pending-future-appointments")
def internal_get_clinic_pending_future_appointments(
    clinic_id: UUID = Path(...),
    db: Session = Depends(get_db),
) -> dict:
    now = datetime.utcnow()
    pending_statuses = {"scheduled", "confirmed", "pending_payment"}
    pending_query = (
        db.query(Appointment)
        .filter(
            Appointment.clinic_id == clinic_id,
            Appointment.status.in_(pending_statuses),
            (
                (Appointment.appointment_date > now.date())
                | (
                    (Appointment.appointment_date == now.date())
                    & (Appointment.start_time >= now.time())
                )
            ),
        )
    )
    count = pending_query.count()
    return {"pending_future_appointments": count}


@router.get("/appointments/pending-future")
def internal_get_doctor_pending_future_appointments(
    doctor_id: UUID = Query(..., description="Doctor UUID"),
    clinic_id: UUID = Query(..., description="Clinic UUID"),
    db: Session = Depends(get_db),
) -> dict:
    now = datetime.utcnow()
    pending_statuses = {"scheduled", "confirmed", "pending_payment"}
    pending_query = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.clinic_id == clinic_id,
            Appointment.status.in_(pending_statuses),
            (
                (Appointment.appointment_date > now.date())
                | (
                    (Appointment.appointment_date == now.date())
                    & (Appointment.start_time >= now.time())
                )
            ),
        )
    )
    count = pending_query.count()
    return {"pending_future_appointments": count}


@router.get("/appointments/pending-future/doctor/{doctor_id}")
def internal_get_doctor_pending_future_appointments_all(
    doctor_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    now = datetime.utcnow()
    pending_statuses = {"scheduled", "confirmed", "pending_payment"}
    pending_query = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status.in_(pending_statuses),
            (
                (Appointment.appointment_date > now.date())
                | (
                    (Appointment.appointment_date == now.date())
                    & (Appointment.start_time >= now.time())
                )
            ),
        )
    )
    count = pending_query.count()
    return {"pending_future_appointments": count}


@router.get("/appointments/pending-future/patient/user/{user_id}")
def internal_get_patient_pending_future_appointments_by_user(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    patient = db.query(Patient).filter(Patient.user_id == user_id).first()
    if not patient:
        return {"pending_future_appointments": 0}

    now = datetime.utcnow()
    pending_statuses = {"scheduled", "confirmed", "pending_payment"}
    pending_query = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient.patient_id,
            Appointment.status.in_(pending_statuses),
            (
                (Appointment.appointment_date > now.date())
                | (
                    (Appointment.appointment_date == now.date())
                    & (Appointment.start_time >= now.time())
                )
            ),
        )
    )
    count = pending_query.count()
    return {"pending_future_appointments": count}


@router.get("/clinics/{clinic_id}/dashboard")
def internal_get_clinic_dashboard(
    clinic_id: UUID = Path(...),
    db: Session = Depends(get_db),
) -> dict:
    today = datetime.utcnow().date()
    base_query = db.query(Appointment).filter(
        Appointment.clinic_id == clinic_id,
        Appointment.appointment_date == today,
    )
    total_appointments = base_query.count()
    completed_consultations = base_query.filter(Appointment.status == "completed").count()
    cancellations = base_query.filter(Appointment.status == "cancelled").count()
    return {
        "total_appointments": total_appointments,
        "completed_consultations": completed_consultations,
        "cancellations": cancellations,
    }


@router.get("/platform/active-patients")
def internal_get_active_patients(db: Session = Depends(get_db)) -> dict:
    cutoff = (datetime.utcnow() - timedelta(days=30)).date()
    active_statuses = {"scheduled", "confirmed", "in_progress", "arrived", "completed", "no_show"}
    query = (
        db.query(Appointment.patient_id)
        .filter(
            Appointment.appointment_date >= cutoff,
            Appointment.status.in_(active_statuses),
        )
        .distinct()
    )
    return {"active_patients": query.count()}


@router.get("/platform/daily-bookings")
def internal_get_daily_bookings(
    target_date: date | None = Query(None, description="Target date for daily bookings."),
    db: Session = Depends(get_db),
) -> dict:
    booking_date = target_date or datetime.utcnow().date()
    query = (
        db.query(Appointment)
        .filter(
            Appointment.appointment_date == booking_date,
            Appointment.status != "cancelled",
        )
    )
    return {"daily_bookings": query.count()}


@router.get("/policies/effective")
def internal_get_effective_policy(db: Session = Depends(get_db)) -> dict:
    policy = resolve_effective_policy(db)
    return {
        "policy_id": policy.policy_id,
        "cancellation_window_hours": policy.cancellation_window_hours,
        "reschedule_window_hours": policy.reschedule_window_hours,
        "advance_booking_days": policy.advance_booking_days,
        "no_show_grace_period_minutes": policy.no_show_grace_period_minutes,
        "max_reschedules": policy.max_reschedules,
    }
