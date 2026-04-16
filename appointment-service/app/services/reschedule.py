"""Reschedule appointment logic."""
from __future__ import annotations
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.config import settings
from app.models import Appointment, AppointmentStatusHistory, Patient
from app.schemas import RescheduleAppointmentRequest, BookAppointmentResponse, BookAppointmentRequest
from app.services.booking import _validate_slot_with_doctor_service, OCCUPIED_STATUSES

def reschedule_appointment(
    db: Session,
    *,
    patient_user_id: str,
    appointment_id: UUID,
    request: RescheduleAppointmentRequest,
) -> BookAppointmentResponse:
    """
    1. Load Appointment. Verify Ownership.
    2. Halt if non-reschedulable status.
    3. Cutoff window validation.
    4. Doctor validate-slot via doctor-service.
    5. Collision check for the new slot.
    6. Write history logging (old->resched->new).
    7. Update appointments row inline.
    """
    # ------------------------------------------------------------------
    # Step 1: Establish Patient context
    # ------------------------------------------------------------------
    try:
        patient_uuid = UUID(patient_user_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing patient user ID."
        ) from exc

    patient = db.query(Patient).filter(Patient.user_id == patient_uuid).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found."
        )

    # ------------------------------------------------------------------
    # Step 2: Load Appointment & Validate State
    # ------------------------------------------------------------------
    appt = db.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found."
        )

    if appt.patient_id != patient.patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only reschedule your own appointments."
        )

    if appt.status not in ["scheduled", "confirmed", "pending_payment"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reschedule an appointment in '{appt.status}' state."
        )

    # ------------------------------------------------------------------
    # Step 3: Cutoff Math Validation
    # ------------------------------------------------------------------
    # Construct completely localized naive datetime for current appointment start
    appt_dt = datetime.combine(appt.appointment_date, appt.start_time)
    now_dt = datetime.now()  # Assuming server local timezone is correctly handled or UTC. 

    if (appt_dt - now_dt) < timedelta(hours=settings.RESCHEDULE_WINDOW_HOURS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointments can only be rescheduled at least {settings.RESCHEDULE_WINDOW_HOURS} hours in advance."
        )

    # ------------------------------------------------------------------
    # Step 4: Validate proposed slot via Doctor Service
    # ------------------------------------------------------------------
    val_req = BookAppointmentRequest(
        doctor_id=appt.doctor_id,
        clinic_id=appt.clinic_id,
        date=request.new_date,
        start_time=request.new_start_time,
        consultation_type=request.new_consultation_type,
    )
    
    slot_info = _validate_slot_with_doctor_service(val_req)

    if not slot_info.get("valid"):
        reason = slot_info.get("reason", "Selected slot is not valid")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=reason)

    end_time_str = slot_info["end_time"]
    doctor_name = slot_info["doctor_name"]
    clinic_name = slot_info["clinic_name"]
    consultation_fee = slot_info.get("consultation_fee")

    # ------------------------------------------------------------------
    # Step 5: Collision Verification
    # ------------------------------------------------------------------
    new_start_time_obj = datetime.strptime(request.new_start_time, "%H:%M").time()
    new_end_time_obj = datetime.strptime(end_time_str, "%H:%M").time()

    collision = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == appt.doctor_id,
            Appointment.clinic_id == appt.clinic_id,
            Appointment.appointment_date == request.new_date,
            Appointment.start_time == new_start_time_obj,
            Appointment.status.in_(OCCUPIED_STATUSES),
            Appointment.appointment_id != appt.appointment_id,  # Don't collide with self
        )
        .first()
    )

    if collision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This slot is already booked. Please choose another time."
        )

    # ------------------------------------------------------------------
    # Step 6: Determine Pricing / New Status
    # ------------------------------------------------------------------
    new_status = appt.status
    new_payment_status = appt.payment_status

    # If the patient reschedules from a free consultation to a paid one
    if consultation_fee and consultation_fee > 0 and appt.payment_status == "not_required":
         new_status = "pending_payment"
         new_payment_status = "pending"
    # Or if a reschedule fee is required, that would trigger pending_payment.
    # TODO: Calculate if any rescheduling fees apply by querying payment-service

    # ------------------------------------------------------------------
    # Step 7: History Auditing
    # ------------------------------------------------------------------
    old_status = appt.status
    
    # Audit 1: Current -> Rescheduled
    history_reschedule = AppointmentStatusHistory(
        appointment_id=appt.appointment_id,
        old_status=old_status,
        new_status="rescheduled",
        changed_by=str(patient.patient_id),
        reason="Patient initiated reschedule"
    )
    db.add(history_reschedule)
    
    # Audit 2: Rescheduled -> Final Updated State 
    if new_status != "rescheduled":
        history_final = AppointmentStatusHistory(
            appointment_id=appt.appointment_id,
            old_status="rescheduled",
            new_status=new_status,
            changed_by=str(patient.patient_id),
            reason="Reschedule finalized natively"
        )
        db.add(history_final)

    # ------------------------------------------------------------------
    # Step 8: Inline Mutate Database Record
    # ------------------------------------------------------------------
    # Save the original temporal coordinates
    appt.rescheduled_from_date = appt.appointment_date
    appt.rescheduled_from_start_time = appt.start_time

    # Apply the new temporal coordinates
    appt.appointment_date = request.new_date
    appt.start_time = new_start_time_obj
    appt.end_time = new_end_time_obj
    appt.appointment_type = request.new_consultation_type
    
    appt.status = new_status
    appt.payment_status = new_payment_status
    
    # Execute the transation securely
    db.commit()
    db.refresh(appt)
    
    # TODO: Emit logic against Notification-Service via webhooks to update Doctor and Patient.

    return BookAppointmentResponse(
        appointment_id=appt.appointment_id,
        doctor_name=doctor_name,
        clinic_name=clinic_name,
        date=appt.appointment_date,
        start_time=appt.start_time.strftime("%H:%M"),
        end_time=appt.end_time.strftime("%H:%M"),
        consultation_type=appt.appointment_type,
        status=appt.status,
        payment_status=appt.payment_status,
        consultation_fee=consultation_fee,
        message=f"Appointment successfully rescheduled to {appt.appointment_date.strftime('%Y-%m-%d')} at {appt.start_time.strftime('%H:%M')}."
    )
