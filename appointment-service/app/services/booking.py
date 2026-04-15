"""Core booking logic — slot validation, collision check, idempotency."""
from __future__ import annotations
from datetime import date, time, datetime
from typing import Optional
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Appointment, Patient
from app.schemas import BookAppointmentRequest, BookAppointmentResponse


# Statuses that occupy a slot (same as in internal.py)
OCCUPIED_STATUSES = {"scheduled", "confirmed", "pending_payment", "in_progress"}


def book_appointment(
    db: Session,
    *,
    patient_id: str,
    request: BookAppointmentRequest,
    idempotency_key: Optional[str] = None,
) -> BookAppointmentResponse:
    """
    1. Idempotency check
    2. Validate slot via doctor-service
    3. Double-book collision check
    4. Create appointment
    5. Return response
    """

    # ------------------------------------------------------------------
    # Step 1: Idempotency — if the key already exists, return existing
    # ------------------------------------------------------------------
    if idempotency_key:
        existing = (
            db.query(Appointment)
            .filter(Appointment.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            # Return the persisted appointment as-is for idempotent replays.
            # Do not re-validate or re-fetch metadata using the new request,
            # because that can make the response inconsistent with the stored
            # appointment and can fail even though the booking already exists.
            return BookAppointmentResponse(
                appointment_id=existing.appointment_id,
                doctor_name="",
                clinic_name="",
                date=existing.appointment_date,
                start_time=existing.start_time.strftime("%H:%M"),
                end_time=existing.end_time.strftime("%H:%M"),
                consultation_type=existing.appointment_type,
                status=existing.status,
                payment_status=existing.payment_status,
                consultation_fee=None,
                message="Appointment already exists (idempotent request).",
            )

    # ------------------------------------------------------------------
    # Step 2: Validate slot via doctor-service
    # ------------------------------------------------------------------
    slot_info = _validate_slot_with_doctor_service(request)

    if not slot_info.get("valid"):
        reason = slot_info.get("reason", "Slot is not valid")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=reason)

    end_time_str: str = slot_info["end_time"]
    doctor_name: str = slot_info["doctor_name"]
    clinic_name: str = slot_info["clinic_name"]
    consultation_fee: Optional[float] = slot_info.get("consultation_fee")

    # ------------------------------------------------------------------
    # Step 3: Double-book collision check
    # ------------------------------------------------------------------
    start_time_obj = datetime.strptime(request.start_time, "%H:%M").time()
    end_time_obj = datetime.strptime(end_time_str, "%H:%M").time()

    collision = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == request.doctor_id,
            Appointment.clinic_id == request.clinic_id,
            Appointment.appointment_date == request.date,
            Appointment.start_time < end_time_obj,
            Appointment.end_time > start_time_obj,
            Appointment.status.in_(OCCUPIED_STATUSES),
        )
        .first()
    )

    if collision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This slot is already booked. Please choose another time.",
        )

    # ------------------------------------------------------------------
    # Step 4: Ensure patient record exists (auto-create on first booking)
    # ------------------------------------------------------------------
    existing_patient = (
        db.query(Patient)
        .filter(Patient.user_id == patient_id)
        .first()
    )
    if not existing_patient:
        existing_patient = Patient(
            user_id=patient_id,
            full_name="Patient",  # will be updated via patient-service later
        )
        db.add(existing_patient)
        db.flush()  # get patient_id without committing

    # ------------------------------------------------------------------
    # Step 5: Create appointment
    # ------------------------------------------------------------------
    # Determine initial statuses based on consultation fee
    if consultation_fee and consultation_fee > 0:
        appt_status = "pending_payment"
        payment_status = "pending"
        message = f"Appointment created. Payment of Rs {consultation_fee:.2f} is required to confirm."
    else:
        appt_status = "confirmed"
        payment_status = "not_required"
        message = "Appointment confirmed successfully."

    appointment = Appointment(
        patient_id=existing_patient.patient_id,
        doctor_id=request.doctor_id,
        clinic_id=request.clinic_id,
        appointment_type=request.consultation_type,
        appointment_date=request.date,
        start_time=start_time_obj,
        end_time=end_time_obj,
        status=appt_status,
        payment_status=payment_status,
        idempotency_key=idempotency_key,
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    # ------------------------------------------------------------------
    # Step 5: TODO — Payment service integration
    # When payment is required (consultation_fee > 0):
    #   - Call POST http://payment-service:8000/internal/payments
    #     with appointment_id, patient_id, amount
    #   - Store returned payment_id
    #   - Payment service will call back to confirm the appointment
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Step 6: TODO — Notification service integration
    # When appointment is confirmed (no payment required):
    #   - Call POST http://notification-service:8000/internal/notifications
    #     with user_id, channel, payload (appointment details)
    #   - Fire-and-forget, do not block on response
    # ------------------------------------------------------------------

    return BookAppointmentResponse(
        appointment_id=appointment.appointment_id,
        doctor_name=doctor_name,
        clinic_name=clinic_name,
        date=appointment.appointment_date,
        start_time=appointment.start_time.strftime("%H:%M"),
        end_time=appointment.end_time.strftime("%H:%M"),
        consultation_type=appointment.appointment_type,
        status=appointment.status,
        payment_status=appointment.payment_status,
        consultation_fee=consultation_fee,
        message=message,
    )


def _validate_slot_with_doctor_service(request: BookAppointmentRequest) -> dict:
    """Call doctor-service to validate the slot is bookable."""
    url = f"{settings.DOCTOR_SERVICE_URL}/internal/doctors/{request.doctor_id}/validate-slot"
    params = {
        "clinic_id": str(request.clinic_id),
        "date": request.date.isoformat(),
        "start_time": request.start_time,
        "consultation_type": request.consultation_type,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Doctor service validation error: {exc.response.status_code}",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Doctor service is currently unavailable. Please try again later.",
        )
