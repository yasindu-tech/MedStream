"""Doctor profile retrieval with slot computation."""
from __future__ import annotations
from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Doctor, Clinic, DoctorClinicAssignment, DoctorAvailability
from app.schemas import (
    ClinicDetail,
    AvailabilityWindow,
    DoctorProfileClinic,
    DoctorProfileResponse,
    SlotItem,
)
from app.services.appointment_client import get_booked_slots, get_effective_policy
from app.services.slots import generate_slots


def get_doctor_profile(
    db: Session,
    doctor_id: UUID,
    target_date: Optional[date] = None,
) -> Optional[DoctorProfileResponse]:
    """
    Load a doctor's full profile with clinic details and availability.

    Returns None if the doctor is not found, inactive, or unverified.
    When target_date is provided, computes available slots for that day
    (respecting the advance booking window and excluding booked slots).
    """

    # 1. Load the doctor
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
        return None

    # 2. Determine day-of-week and validate booking window
    day_of_week: Optional[str] = None
    date_within_window = False
    if target_date:
        day_of_week = target_date.strftime("%A").lower()
        policy = get_effective_policy()
        max_date = date.today() + timedelta(days=policy["advance_booking_days"])
        date_within_window = target_date <= max_date and target_date >= date.today()

    # 3. Load active clinic assignments with clinic data
    assignments = (
        db.query(DoctorClinicAssignment, Clinic)
        .join(
            Clinic,
            (Clinic.clinic_id == DoctorClinicAssignment.clinic_id)
            & (Clinic.status == "active"),
        )
        .filter(
            DoctorClinicAssignment.doctor_id == doctor_id,
            DoctorClinicAssignment.status == "active",
        )
        .all()
    )

    # 4. For each clinic, load availability and compute slots
    profile_clinics: List[DoctorProfileClinic] = []

    for assignment, clinic in assignments:
        # Load ALL active availability rows for this doctor+clinic
        avail_rows = (
            db.query(DoctorAvailability)
            .filter(
                DoctorAvailability.doctor_id == doctor_id,
                DoctorAvailability.clinic_id == clinic.clinic_id,
                DoctorAvailability.status == "active",
            )
            .all()
        )

        # Build the full weekly schedule
        availability_windows = [
            AvailabilityWindow(
                day_of_week=a.day_of_week,
                start_time=a.start_time,
                end_time=a.end_time,
                slot_duration=a.slot_duration,
                consultation_type=a.consultation_type,
            )
            for a in avail_rows
        ]

        # Compute slots only if a valid date was provided
        slots: List[SlotItem] = []
        if target_date and date_within_window and day_of_week:
            matching = [a for a in avail_rows if a.day_of_week == day_of_week]
            booked = get_booked_slots(
                str(doctor_id), str(clinic.clinic_id), target_date
            )
            booked_starts = {b.start_time for b in booked}
            for a in matching:
                slots.extend(
                    generate_slots(a.start_time, a.end_time, a.slot_duration, booked_starts)
                )

        clinic_detail = ClinicDetail(
            clinic_id=clinic.clinic_id,
            clinic_name=clinic.clinic_name,
            address=clinic.address,
            phone=clinic.phone,
            email=clinic.email,
        )

        profile_clinics.append(
            DoctorProfileClinic(
                clinic=clinic_detail,
                availability=availability_windows,
                available_slots=slots,
                has_slots=len(slots) > 0,
            )
        )

    # 5. Determine profile completeness
    profile_complete = all([
        doctor.full_name,
        doctor.specialization,
        doctor.bio,
        doctor.experience_years is not None,
    ])

    # 6. Build the response
    fee = str(doctor.consultation_fee) if doctor.consultation_fee is not None else None

    return DoctorProfileResponse(
        doctor_id=doctor.doctor_id,
        full_name=doctor.full_name,
        specialization=doctor.specialization,
        bio=doctor.bio,
        experience_years=doctor.experience_years,
        qualifications=doctor.qualifications,
        consultation_mode=doctor.consultation_mode,
        medical_registration_no=doctor.medical_registration_no,
        verification_status=doctor.verification_status,
        profile_image_url=doctor.profile_image_url,
        consultation_fee=fee,
        profile_complete=profile_complete,
        clinics=profile_clinics,
    )
