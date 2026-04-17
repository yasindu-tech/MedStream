"""Internal router — service-to-service calls only (no JWT needed).

Provides booked slot data to doctor-service for slot computation.
Not exposed through the nginx gateway.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment
from app.schemas import AppointmentOutcomeResponse, BookedSlotResponse, InternalNoShowRequest, InternalTechnicalFailureRequest, MarkArrivedRequest
from app.services.outcome import mark_arrived, mark_no_show, mark_technical_failure
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


@router.post("/appointments/{appointment_id}/mark-technical-failure", response_model=AppointmentOutcomeResponse)
def internal_mark_technical_failure(
    request: InternalTechnicalFailureRequest,
    appointment_id: UUID = Path(...),
    db: Session = Depends(get_db),
) -> AppointmentOutcomeResponse:
    appt = mark_technical_failure(
        db,
        appointment_id=appointment_id,
        actor_role=request.mark_by,
        actor_user_id="internal-system",
        reason=request.reason,
    )
    return AppointmentOutcomeResponse(
        appointment_id=appt.appointment_id,
        status=appt.status,
        changed_at=(appt.technical_failure_at or datetime.now()).isoformat(),
        message="Appointment marked as technical failure",
    )


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


class _PaymentStatusUpdate(BaseModel):
    payment_status: str
    transaction_reference: str | None = None


@router.patch("/appointments/{appointment_id}/payment-status")
def internal_update_payment_status(
    body: _PaymentStatusUpdate,
    appointment_id: UUID = Path(...),
    db: Session = Depends(get_db),
) -> dict:
    """
    Called by payment-service after Stripe confirms/fails a payment.
    Transitions the appointment status accordingly.
    """
    appointment = (
        db.query(Appointment)
        .filter(Appointment.appointment_id == appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if body.payment_status == "paid":
        appointment.payment_status = "paid"
        appointment.status = "confirmed"
        db.commit()
        return {
            "appointment_id": str(appointment_id),
            "status": appointment.status,
            "payment_status": appointment.payment_status,
            "message": "Appointment confirmed after successful payment.",
        }
    elif body.payment_status == "failed":
        appointment.payment_status = "failed"
        db.commit()
        return {
            "appointment_id": str(appointment_id),
            "status": appointment.status,
            "payment_status": appointment.payment_status,
            "message": "Payment failed. Patient may retry.",
        }
    else:
        raise HTTPException(status_code=400, detail=f"Invalid payment_status: {body.payment_status}")

