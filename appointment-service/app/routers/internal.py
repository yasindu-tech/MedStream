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
from app.models import Appointment, AppointmentStatusHistory, Patient
from app.schemas import (
    AppointmentOutcomeResponse,
    BookedSlotResponse,
    ClinicOperationalDashboardResponse,
    InternalNoShowRequest,
    InternalTechnicalFailureRequest,
    MarkArrivedRequest,
)
from app.services.outcome import mark_arrived, mark_no_show, mark_technical_failure
from app.services.policy import resolve_effective_policy
from app.schemas import (
    InternalPostConsultationContextResponse,
    InternalPreConsultationContextRequest,
    InternalPreConsultationContextResponse,
)
from app.services.consultation import get_post_consultation_context, get_pre_consultation_context

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


@router.get("/clinics/{clinic_id}/appointments")
def internal_list_clinic_appointments(
    clinic_id: UUID = Path(..., description="Clinic UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    date: date | None = Query(None, description="Filter by appointment date (YYYY-MM-DD)"),
    status: str | None = Query(None, description="Filter by appointment status"),
    consultation_type: str | None = Query(None, description="Filter by consultation type"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Return paginated appointments for a clinic.
    Called by clinic-service to serve the clinic admin appointments view.
    """

    query = (
        db.query(Appointment, Patient)
        .join(Patient, Appointment.patient_id == Patient.patient_id)
        .filter(Appointment.clinic_id == clinic_id)
    )

    if date:
        query = query.filter(Appointment.appointment_date == date)
    if status:
        query = query.filter(Appointment.status == status)
    if consultation_type:
        query = query.filter(Appointment.appointment_type == consultation_type)

    query = query.order_by(Appointment.appointment_date, Appointment.start_time)
    total = query.count()
    offset = (page - 1) * size
    rows = query.offset(offset).limit(size).all()

    items = [
        {
            "appointment_id": str(appt.appointment_id),
            "doctor_id": str(appt.doctor_id) if appt.doctor_id else str(UUID(int=0)),
            "doctor_name": appt.doctor_name,
            "clinic_id": str(appt.clinic_id) if appt.clinic_id else str(clinic_id),
            "clinic_name": appt.clinic_name,
            "patient_id": str(appt.patient_id),
            "patient_name": pat.full_name,
            "date": appt.appointment_date.isoformat(),
            "start_time": appt.start_time.strftime("%H:%M"),
            "end_time": appt.end_time.strftime("%H:%M"),
            "status": appt.status,
            "payment_status": appt.payment_status,
            "consultation_type": appt.appointment_type,
        }
        for appt, pat in rows
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "has_more": (offset + len(items)) < total,
    }


@router.get("/clinics/{clinic_id}/dashboard", response_model=ClinicOperationalDashboardResponse)
def internal_clinic_operational_dashboard(
    clinic_id: UUID = Path(..., description="Clinic UUID"),
    target_date: date | None = Query(None, description="Target date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> ClinicOperationalDashboardResponse:
    data = get_clinic_operational_dashboard(db=db, clinic_id=clinic_id, target_date=target_date)
    return ClinicOperationalDashboardResponse(**data)


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
        old_status = appointment.status
        appointment.payment_status = "paid"
        appointment.status = "confirmed"
        
        # Record history
        history = AppointmentStatusHistory(
            appointment_id=appointment_id,
            old_status=old_status,
            new_status="confirmed",
            changed_by="payment-service",
            reason="Payment confirmed via Stripe"
        )
        db.add(history)
        
        db.commit()
        return {
            "appointment_id": str(appointment_id),
            "status": appointment.status,
            "payment_status": appointment.payment_status,
            "message": "Appointment confirmed after successful payment.",
        }
    elif body.payment_status == "failed":
        old_status = appointment.status
        appointment.payment_status = "failed"
        
        # Record history for payment failure
        history = AppointmentStatusHistory(
            appointment_id=appointment_id,
            old_status=old_status,
            new_status=old_status,  # Status doesn't change, but we log the payment failure event
            changed_by="payment-service",
            reason="Payment failed via Stripe"
        )
        db.add(history)
        
        db.commit()
        return {
            "appointment_id": str(appointment_id),
            "status": appointment.status,
            "payment_status": appointment.payment_status,
            "message": "Payment failed. Patient may retry.",
        }
    else:
        raise HTTPException(status_code=400, detail=f"Invalid payment_status: {body.payment_status}")


@router.get("/appointments/{appointment_id}")
def internal_get_appointment_details(
    appointment_id: UUID = Path(...),
    db: Session = Depends(get_db),
) -> dict:
    """Returns basic appointment details for other services (e.g. payment-service)."""
    appointment = (
        db.query(Appointment)
        .filter(Appointment.appointment_id == appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    return {
        "appointment_id": str(appointment.appointment_id),
        "doctor_name": appointment.doctor_name,
        "appointment_date": appointment.appointment_date.isoformat(),
        "start_time": appointment.start_time.strftime("%H:%M"),
        "clinic_name": appointment.clinic_name,
    }


@router.post(
    "/appointments/{appointment_id}/pre-consultation-context",
    response_model=InternalPreConsultationContextResponse,
)
def internal_get_pre_consultation_context(
    request: InternalPreConsultationContextRequest,
    appointment_id: UUID = Path(...),
    db: Session = Depends(get_db),
) -> InternalPreConsultationContextResponse:
    payload = get_pre_consultation_context(
        db,
        appointment_id=appointment_id,
        doctor_user_id=request.doctor_user_id,
        recent_limit=request.recent_limit,
    )
    return InternalPreConsultationContextResponse(**payload)


@router.get(
    "/appointments/{appointment_id}/post-consultation-context",
    response_model=InternalPostConsultationContextResponse,
)
def internal_get_post_consultation_context(
    appointment_id: UUID = Path(...),
    db: Session = Depends(get_db),
) -> InternalPostConsultationContextResponse:
    payload = get_post_consultation_context(
        db,
        appointment_id=appointment_id,
    )
    return InternalPostConsultationContextResponse(**payload)

