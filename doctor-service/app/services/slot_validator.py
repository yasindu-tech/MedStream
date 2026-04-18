"""Lightweight slot validation for the booking flow."""
from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Doctor, Clinic, DoctorClinicAssignment, DoctorAvailability


def validate_slot(
    db: Session,
    *,
    doctor_id: UUID,
    clinic_id: UUID,
    target_date: date,
    start_time: str,
    consultation_type: str,
    is_followup: bool = False,
) -> dict:
    """
    Validate that a specific slot is bookable.

    Returns dict with:
      - valid: bool
      - reason: str (if invalid)
      - doctor_name, clinic_name, consultation_fee, end_time, slot_duration (if valid)
    """

    # 1. Doctor must be active + verified
    doctor = (
        db.query(Doctor)
        .filter(
            Doctor.doctor_id == doctor_id,
            Doctor.status == "active",
            Doctor.verification_status == "verified",
        )
        .first()
    )
    if not doctor:
        return {"valid": False, "reason": "Doctor not found, inactive, or unverified"}

    # 2. Clinic assignment must be active, clinic must be active
    assignment = (
        db.query(DoctorClinicAssignment, Clinic)
        .join(
            Clinic,
            (Clinic.clinic_id == DoctorClinicAssignment.clinic_id)
            & (Clinic.status == "active"),
        )
        .filter(
            DoctorClinicAssignment.doctor_id == doctor_id,
            DoctorClinicAssignment.clinic_id == clinic_id,
            DoctorClinicAssignment.status == "active",
        )
        .first()
    )
    if not assignment:
        return {"valid": False, "reason": "Doctor is not assigned to this clinic or clinic is inactive"}

    _, clinic = assignment

    # 3. Availability window must exist for this day + cover the start_time
    day_of_week = target_date.strftime("%A").lower()

    avail_rows = (
        db.query(DoctorAvailability)
        .filter(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.clinic_id == clinic_id,
            DoctorAvailability.day_of_week == day_of_week,
            DoctorAvailability.status == "active",
        )
        .all()
    )

    if not avail_rows:
        return {"valid": False, "reason": f"Doctor has no availability on {day_of_week}"}

    # Validate start_time format before processing availability rows
    try:
        slot_start = datetime.strptime(start_time, "%H:%M")
    except (ValueError, TypeError):
        return {"valid": False, "reason": f"Invalid time format: '{start_time}'. Expected HH:MM."}

    # If it's a follow-up, we are more lenient.
    # We allow the doctor to book even if no active availability record exists for this specific day/type.
    if is_followup:
        # We still need a default slot duration. We'll try to find any availability for this doctor at this clinic,
        # otherwise default to 15 mins.
        any_avail = db.query(DoctorAvailability).filter(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.clinic_id == clinic_id
        ).first()
        duration = any_avail.slot_duration if any_avail else 15
        slot_end = slot_start + timedelta(minutes=duration)
        
        fee = float(doctor.consultation_fee) if doctor.consultation_fee is not None else None
        return {
            "valid": True,
            "doctor_name": doctor.full_name,
            "clinic_name": clinic.clinic_name,
            "consultation_fee": fee,
            "end_time": slot_end.strftime("%H:%M"),
            "slot_duration": duration,
        }

    # 4. Find the availability row that covers this start_time and matches consultation_type
    for avail in avail_rows:
        # Check consultation_type match
        if avail.consultation_type and avail.consultation_type != consultation_type:
            continue

        # Check that start_time falls within the window and aligns to slot grid
        window_start = datetime.strptime(avail.start_time, "%H:%M")
        window_end = datetime.strptime(avail.end_time, "%H:%M")
        slot_start = datetime.strptime(start_time, "%H:%M")
        slot_end = slot_start + timedelta(minutes=avail.slot_duration)

        if slot_start < window_start or slot_end > window_end:
            continue

        # Verify alignment to the slot grid
        minutes_from_start = (slot_start - window_start).total_seconds() / 60
        if minutes_from_start % avail.slot_duration != 0:
            continue

        # Valid slot found
        fee = float(doctor.consultation_fee) if doctor.consultation_fee is not None else None
        return {
            "valid": True,
            "doctor_name": doctor.full_name,
            "clinic_name": clinic.clinic_name,
            "consultation_fee": fee,
            "end_time": slot_end.strftime("%H:%M"),
            "slot_duration": avail.slot_duration,
        }

    # If we get here, no matching availability window was found
    # Check if it's a consultation_type mismatch specifically.
    # A NULL consultation_type is treated as a wildcard elsewhere in this
    # function, so it must also count as offering all consultation types here.
    has_wildcard_type = any(a.consultation_type is None for a in avail_rows)
    available_types = {a.consultation_type for a in avail_rows if a.consultation_type is not None}
    if not has_wildcard_type and consultation_type not in available_types:
        return {
            "valid": False,
            "reason": f"Doctor does not offer '{consultation_type}' at this clinic. Available: {list(available_types)}",
        }

    return {"valid": False, "reason": "Selected time slot is not within any availability window"}
