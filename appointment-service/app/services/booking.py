"""Core booking logic — slot validation, collision check, idempotency."""
from __future__ import annotations
from datetime import date, time, datetime, timedelta
from typing import Optional
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Appointment, Patient
from app.schemas import BookAppointmentRequest, BookAppointmentResponse
from app.services.policy import resolve_effective_policy
from app.services.telemedicine_client import provision_session_for_appointment


# Statuses that occupy a slot (same as in internal.py)
OCCUPIED_STATUSES = {"scheduled", "pending_doctor", "confirmed", "pending_payment", "in_progress", "arrived"}


def book_appointment(
    db: Session,
    *,
    patient_id: str,
    request: BookAppointmentRequest,
    idempotency_key: Optional[str] = None,
) -> BookAppointmentResponse:
    """
    1. Idempotency check (scoped to patient)
    2. Validate slot via doctor-service
    3. Double-book collision check (time-range overlap)
    4. Create appointment
    5. Return response
    """

    # ------------------------------------------------------------------
    # Step 0: Resolve patient record early so idempotency is scoped
    # ------------------------------------------------------------------
    existing_patient = (
        db.query(Patient)
        .filter(Patient.user_id == patient_id)
        .first()
    )

    # ------------------------------------------------------------------
    # Step 1: Idempotency — scoped to the authenticated patient
    # ------------------------------------------------------------------
    if idempotency_key and existing_patient:
        existing = (
            db.query(Appointment)
            .filter(
                Appointment.patient_id == existing_patient.patient_id,
                Appointment.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing:
            # Verify the stored appointment matches the current request
            if (
                existing.doctor_id != request.doctor_id
                or existing.clinic_id != request.clinic_id
                or existing.appointment_date != request.date
                or existing.start_time != _parse_time(request.start_time)
                or existing.appointment_type != request.consultation_type
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency key already used for a different booking request.",
                )

            # Return the persisted appointment as-is for idempotent replays.
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
    # Step 2: Validate policy-based advance booking window
    # ------------------------------------------------------------------
    effective_policy = resolve_effective_policy(db)
    max_date = date.today() + timedelta(days=effective_policy.advance_booking_days)
    if request.date < date.today() or request.date > max_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointments can only be booked up to {effective_policy.advance_booking_days} days in advance.",
        )

    # ------------------------------------------------------------------
    # Step 3: Validate slot via doctor-service
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
    # Step 4: Double-book collision check (time-range overlap)
    # ------------------------------------------------------------------
    start_time_obj = _parse_time(request.start_time)
    end_time_obj = _parse_time(end_time_str)

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
    # Step 5: Ensure patient record exists (auto-create on first booking)
    # ------------------------------------------------------------------
    if not existing_patient:
        existing_patient = Patient(
            user_id=patient_id,
            full_name="Patient",  # will be updated via patient-service later
        )
        db.add(existing_patient)
        db.flush()  # get patient_id without committing

    # ------------------------------------------------------------------
    # Step 6: Create appointment request
    # ------------------------------------------------------------------
    if consultation_fee and consultation_fee > 0:
        appt_status = "pending_doctor"
        payment_status = "pending"
        message = f"Appointment request submitted. Awaiting doctor approval and payment of Rs {consultation_fee:.2f}."
    else:
        appt_status = "pending_doctor"
        payment_status = "not_required"
        message = "Appointment request submitted. Awaiting doctor approval."

    appointment = Appointment(
        patient_id=existing_patient.patient_id,
        doctor_id=request.doctor_id,
        doctor_name=doctor_name,
        clinic_id=request.clinic_id,
        clinic_name=clinic_name,
        appointment_type=request.consultation_type,
        appointment_date=request.date,
        start_time=start_time_obj,
        end_time=end_time_obj,
        status=appt_status,
        payment_status=payment_status,
        policy_id=UUID(effective_policy.policy_id) if effective_policy.policy_id else None,
        idempotency_key=idempotency_key,
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    if appointment.appointment_type.lower() in {"telemedicine", "virtual"}:
        provision_session_for_appointment(
            appointment.appointment_id,
            appointment.appointment_type,
        )

    _emit_booking_notification_event(
        appointment=appointment,
        patient_user_id=patient_id,
        patient_name=existing_patient.full_name if existing_patient else "Patient",
        patient_phone=existing_patient.phone if existing_patient else None,
    )

    # ------------------------------------------------------------------
    # Step 7: Payment service integration
    # When payment is required (consultation_fee > 0):
    #   - Call POST http://payment-service:8000/api/payments/
    #     with appointment_id, patient_id, doctor_id, clinic_id, amount
    #   - Store returned payment_id for frontend redirect
    # ------------------------------------------------------------------
    payment_id = None
    if consultation_fee and consultation_fee > 0:
        try:
            with httpx.Client(timeout=10.0) as client:
                pay_resp = client.post(
                    f"{settings.PAYMENT_SERVICE_URL}/api/payments/",
                    json={
                        "appointment_id": str(appointment.appointment_id),
                        "patient_id": patient_id,
                        "doctor_id": str(request.doctor_id),
                        "clinic_id": str(request.clinic_id),
                        "amount": float(consultation_fee),
                        "currency": "LKR",
                    },
                    headers={"Authorization": "Bearer internal-service-call"},
                )
                if pay_resp.status_code in (200, 201):
                    pay_data = pay_resp.json()
                    payment_id = pay_data.get("payment_id")
        except Exception:
            # Payment service unavailable — booking still succeeds with
            # payment_status="pending" so it can be retried later.
            pass

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
        payment_id=payment_id,
        message=message,
    )


def _emit_booking_notification_event(
    *,
    appointment: Appointment,
    patient_user_id: str,
    patient_name: str,
    patient_phone: Optional[str],
) -> None:
    payload = {
        "event_type": "appointment.booked",
        "user_id": patient_user_id,
        "payload": {
            "appointment_id": str(appointment.appointment_id),
            "patient_name": patient_name,
            "doctor_name": appointment.doctor_name,
            "date": appointment.appointment_date.isoformat(),
            "time": appointment.start_time.strftime("%H:%M"),
            "phone": patient_phone,
        },
        "channels": ["sms", "email"],
        "priority": "normal",
    }

    try:
        with httpx.Client(timeout=2.0) as client:
            client.post(f"{settings.NOTIFICATION_SERVICE_URL}/api/notifications/events", json=payload)
    except httpx.RequestError:
        # Booking should fail-open if notification service is temporarily unavailable.
        return


def _parse_time(value: str) -> time:
    """Parse HH:MM string to a time object, raising 422 on invalid format."""
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid time format: '{value}'. Expected HH:MM.",
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
