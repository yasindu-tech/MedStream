"""Doctor profile retrieval with slot computation and audit support."""
from __future__ import annotations
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    Clinic,
    Doctor,
    DoctorAvailability,
    DoctorAvailabilityHistory,
    DoctorClinicAssignment,
    DoctorLeave,
    DoctorProfileHistory,
)
from app.schemas import (
    AvailabilityWindow,
    ClinicDetail,
    DoctorClinicAssignmentItem,
    DoctorProfileClinic,
    DoctorProfileResponse,
    DoctorLeaveRequest,
    DoctorLeaveResponse,
    DoctorLeaveListResponse,
    DoctorProfileClinic,
    DoctorProfileResponse,
    DoctorSearchResult,
    DoctorSearchResponse,
    DoctorAvailabilityResponse,
    DoctorAvailabilityCreateRequest,
    DoctorAvailabilityUpdateRequest,
    DoctorCreateRequest,
    DoctorUpdateRequest,
    DoctorVisibilityRequest,
    DoctorClinicAssignmentListResponse,
    SlotItem,
)
from app.services.appointment_client import (
    get_booked_slots,
    get_effective_policy,
    get_pending_future_appointments,
)
from app.services.auth_client import publish_doctor_event, verify_doctor_registration
from app.services.notification_client import send_notification_event
from app.services.slots import generate_slots

logger = logging.getLogger(__name__)

ALLOWED_CONSULTATION_MODES = {"physical", "telemedicine", "both"}
ALLOWED_SPECIALIZATIONS = {
    "Cardiology",
    "General Practice",
    "Pediatrics",
    "Dermatology",
    "Neurology",
    "Orthopaedics",
    "Psychiatry",
    "Endocrinology",
    "Obstetrics",
    "Gynaecology",
}


def _normalize_consultation_mode(mode: Optional[str]) -> Optional[str]:
    if mode is None:
        return None
    normalized = mode.strip().lower()
    if normalized not in ALLOWED_CONSULTATION_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"consultation_mode must be one of {sorted(ALLOWED_CONSULTATION_MODES)}",
        )
    return normalized


def _normalize_specializations(specializations: Optional[List[str]]) -> Optional[List[str]]:
    if specializations is None:
        return None
    normalized = [spec.strip() for spec in specializations if spec and spec.strip()]
    if not normalized:
        return None
    invalid = [spec for spec in normalized if spec not in ALLOWED_SPECIALIZATIONS]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Specializations must be one of the allowed values: {sorted(ALLOWED_SPECIALIZATIONS)}. Invalid: {invalid}",
        )
    return normalized


def _record_profile_history(
    db: Session,
    doctor_id: UUID,
    field_name: str,
    old_value: Optional[str],
    new_value: Optional[str],
    changed_by: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    history = DoctorProfileHistory(
        doctor_id=doctor_id,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        changed_by=changed_by,
        reason=reason,
    )
    db.add(history)


def _load_doctor(db: Session, doctor_id: UUID) -> Optional[Doctor]:
    return (
        db.query(Doctor)
        .filter(
            Doctor.doctor_id == doctor_id,
            Doctor.status == "active",
            Doctor.verification_status == "verified",
        )
        .first()
    )


def _doctor_has_blocked_leave(db: Session, doctor_id: UUID, target_date: date, clinic_id: UUID) -> List[DoctorLeave]:
    start_of_day = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end_of_day = datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc)
    return (
        db.query(DoctorLeave)
        .filter(
            DoctorLeave.doctor_id == doctor_id,
            DoctorLeave.status == "active",
            (DoctorLeave.clinic_id == clinic_id) | (DoctorLeave.clinic_id.is_(None)),
            DoctorLeave.start_datetime <= end_of_day,
            DoctorLeave.end_datetime >= start_of_day,
        )
        .all()
    )


def _slot_overlaps_leave(start_time: str, end_time: str, leaves: List[DoctorLeave], target_date: date) -> bool:
    slot_start = datetime.strptime(
        f"{target_date.isoformat()} {start_time}", "%Y-%m-%d %H:%M"
    ).replace(tzinfo=timezone.utc)
    slot_end = datetime.strptime(
        f"{target_date.isoformat()} {end_time}", "%Y-%m-%d %H:%M"
    ).replace(tzinfo=timezone.utc)
    for leave in leaves:
        if slot_start < leave.end_datetime and leave.start_datetime < slot_end:
            return True
    return False


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
    doctor = _load_doctor(db, doctor_id)
    if not doctor:
        return None

    day_of_week: Optional[str] = None
    date_within_window = False
    if target_date:
        day_of_week = target_date.strftime("%A").lower()
        policy = get_effective_policy()
        max_date = date.today() + timedelta(days=policy["advance_booking_days"])
        date_within_window = target_date <= max_date and target_date >= date.today()

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

    profile_clinics: List[DoctorProfileClinic] = []

    for assignment, clinic in assignments:
        avail_rows = (
            db.query(DoctorAvailability)
            .filter(
                DoctorAvailability.doctor_id == doctor_id,
                DoctorAvailability.clinic_id == clinic.clinic_id,
                DoctorAvailability.status == "active",
            )
            .all()
        )

        availability_windows = [
            AvailabilityWindow(
                day_of_week=a.day_of_week or a.date.strftime("%A").lower(),
                start_time=a.start_time,
                end_time=a.end_time,
                slot_duration=a.slot_duration,
                consultation_type=a.consultation_type,
            )
            for a in avail_rows
        ]

        slots: List[SlotItem] = []
        if target_date and date_within_window and day_of_week:
            one_time = [a for a in avail_rows if a.date == target_date]
            recurring = [a for a in avail_rows if a.day_of_week == day_of_week]
            booked = get_booked_slots(str(doctor_id), str(clinic.clinic_id), target_date)
            booked_starts = {b.start_time for b in booked}
            leaves = _doctor_has_blocked_leave(db, doctor_id, target_date, clinic.clinic_id)
            for a in recurring + one_time:
                for slot in generate_slots(a.start_time, a.end_time, a.slot_duration, booked_starts):
                    if not _slot_overlaps_leave(slot.start_time, slot.end_time, leaves, target_date):
                        slots.append(slot)

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

    profile_complete = all([
        doctor.full_name,
        doctor.primary_specialization or doctor.specialization,
        doctor.bio,
        doctor.experience_years is not None,
    ])

    fee = str(doctor.consultation_fee) if doctor.consultation_fee is not None else None

    return DoctorProfileResponse(
        doctor_id=doctor.doctor_id,
        full_name=doctor.full_name,
        specialization=doctor.primary_specialization or doctor.specialization,
        specializations=doctor.specializations,
        primary_specialization=doctor.primary_specialization,
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


def _validate_specializations(
    specialization: Optional[str],
    specializations: Optional[List[str]],
    primary_specialization: Optional[str],
) -> tuple[Optional[List[str]], Optional[str]]:
    normalized = None
    if specializations is not None:
        normalized = _normalize_specializations(specializations)
    if specialization and normalized is None:
        normalized = _normalize_specializations([specialization])
    if normalized is not None and primary_specialization:
        if primary_specialization not in normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="primary_specialization must be one of the selected specializations.",
            )
    if normalized is not None and primary_specialization is None:
        primary_specialization = normalized[0]
    return normalized, primary_specialization


def create_doctor_profile(
    db: Session,
    user_id: UUID,
    full_name: str,
    medical_registration_no: Optional[str] = None,
    specialization: Optional[str] = None,
    specializations: Optional[List[str]] = None,
    primary_specialization: Optional[str] = None,
    consultation_mode: Optional[str] = None,
    bio: Optional[str] = None,
    experience_years: Optional[int] = None,
    qualifications: Optional[str] = None,
    profile_image_url: Optional[str] = None,
    consultation_fee: Optional[float] = None,
) -> Doctor:
    verify_doctor_registration(user_id)

    if medical_registration_no:
        duplicate = (
            db.query(Doctor)
            .filter(Doctor.medical_registration_no == medical_registration_no)
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate medical registration number detected.",
            )

    normalized_mode = _normalize_consultation_mode(consultation_mode)
    normalized_specializations, normalized_primary = _validate_specializations(
        specialization,
        specializations,
        primary_specialization,
    )

    doctor = Doctor(
        user_id=user_id,
        full_name=full_name,
        medical_registration_no=medical_registration_no,
        specialization=normalized_primary or specialization,
        specializations=normalized_specializations,
        primary_specialization=normalized_primary,
        consultation_mode=normalized_mode,
        verification_status="verified",
        status="active",
        bio=bio,
        experience_years=experience_years,
        qualifications=qualifications,
        profile_image_url=profile_image_url,
        consultation_fee=consultation_fee,
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    _record_profile_history(
        db,
        doctor_id=doctor.doctor_id,
        field_name="created",
        old_value=None,
        new_value=str({
            "full_name": full_name,
            "specializations": normalized_specializations,
            "primary_specialization": normalized_primary,
        }),
        changed_by=str(user_id),
        reason="Doctor profile created after auth approval",
    )
    db.commit()

    logger.info("Doctor profile created: %s (%s)", doctor.full_name, doctor.doctor_id)
    if doctor.user_id:
        send_notification_event(
            event_type="doctor.profile.created",
            user_id=str(doctor.user_id),
            payload={
                "doctor_name": doctor.full_name,
                "status": "Your doctor profile has been created successfully.",
            },
        )
    publish_doctor_event(
        event_type="doctor.profile.created",
        payload={
            "doctor_id": str(doctor.doctor_id),
            "user_id": str(doctor.user_id),
        },
    )

    return doctor


def update_doctor_profile(
    db: Session,
    doctor_id: UUID,
    full_name: Optional[str] = None,
    medical_registration_no: Optional[str] = None,
    specialization: Optional[str] = None,
    specializations: Optional[List[str]] = None,
    primary_specialization: Optional[str] = None,
    consultation_mode: Optional[str] = None,
    bio: Optional[str] = None,
    experience_years: Optional[int] = None,
    qualifications: Optional[str] = None,
    profile_image_url: Optional[str] = None,
    consultation_fee: Optional[float] = None,
) -> Doctor:
    doctor = db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")

    if medical_registration_no and medical_registration_no != doctor.medical_registration_no:
        duplicate = (
            db.query(Doctor)
            .filter(
                Doctor.doctor_id != doctor.doctor_id,
                Doctor.medical_registration_no == medical_registration_no,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate medical registration number detected.",
            )
        _record_profile_history(
            db,
            doctor_id=doctor.doctor_id,
            field_name="medical_registration_no",
            old_value=doctor.medical_registration_no,
            new_value=medical_registration_no,
            changed_by=str(doctor.user_id) if doctor.user_id else None,
            reason="Medical registration number updated and sent for verification",
        )
        doctor.medical_registration_no = medical_registration_no
        doctor.verification_status = "pending"
        doctor.status = "active"
        if doctor.user_id:
            send_notification_event(
                event_type="doctor.verification.pending",
                user_id=str(doctor.user_id),
                payload={
                    "doctor_name": doctor.full_name,
                    "reason": "Your medical registration number has been updated and is awaiting verification.",
                },
            )

    normalized_mode = _normalize_consultation_mode(consultation_mode)
    normalized_specializations, normalized_primary = _validate_specializations(
        specialization,
        specializations,
        primary_specialization,
    )

    if normalized_specializations is not None:
        _record_profile_history(
            db,
            doctor_id=doctor.doctor_id,
            field_name="specializations",
            old_value=str(doctor.specializations),
            new_value=str(normalized_specializations),
            changed_by=str(doctor.user_id) if doctor.user_id else None,
            reason="Doctor specializations updated",
        )
        doctor.specializations = normalized_specializations
        doctor.primary_specialization = normalized_primary
        doctor.specialization = normalized_primary or (normalized_specializations[0] if normalized_specializations else doctor.specialization)

    if full_name is not None and full_name != doctor.full_name:
        _record_profile_history(
            db,
            doctor_id=doctor.doctor_id,
            field_name="full_name",
            old_value=doctor.full_name,
            new_value=full_name,
            changed_by=str(doctor.user_id) if doctor.user_id else None,
        )
    _apply_update_field(doctor, "full_name", full_name)
    _apply_update_field(doctor, "consultation_mode", normalized_mode)
    _apply_update_field(doctor, "bio", bio)
    _apply_update_field(doctor, "experience_years", experience_years)
    _apply_update_field(doctor, "qualifications", qualifications)
    _apply_update_field(doctor, "profile_image_url", profile_image_url)
    _apply_update_field(doctor, "consultation_fee", consultation_fee)

    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    logger.info("Doctor profile updated: %s (%s)", doctor.full_name, doctor.doctor_id)
    publish_doctor_event(
        event_type="doctor.profile.updated",
        payload={
            "doctor_id": str(doctor.doctor_id),
            "user_id": str(doctor.user_id) if doctor.user_id else "",
        },
    )
    return doctor


def _apply_update_field(obj: Any, field_name: str, value: Any) -> None:
    if value is not None:
        setattr(obj, field_name, value)


def list_doctor_profile_history(db: Session, doctor_id: UUID) -> list[dict[str, str | None]]:
    history_rows = (
        db.query(DoctorProfileHistory)
        .filter(DoctorProfileHistory.doctor_id == doctor_id)
        .order_by(DoctorProfileHistory.changed_at.desc())
        .all()
    )
    return [
        {
            "history_id": row.history_id,
            "field_name": row.field_name,
            "old_value": row.old_value,
            "new_value": row.new_value,
            "changed_by": row.changed_by,
            "reason": row.reason,
            "changed_at": row.changed_at.isoformat(),
        }
        for row in history_rows
    ]


def list_assigned_clinics(db: Session, doctor_id: UUID) -> list[DoctorClinicAssignmentItem]:
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

    return [
        DoctorClinicAssignmentItem(
            clinic_id=clinic.clinic_id,
            clinic_name=clinic.clinic_name,
            address=clinic.address,
            phone=clinic.phone,
            email=clinic.email,
            status=assignment.status,
        )
        for assignment, clinic in assignments
    ]
