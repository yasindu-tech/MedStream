from __future__ import annotations
import logging
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    Doctor,
    DoctorAvailability,
    DoctorAvailabilityHistory,
    DoctorClinicAssignment,
)
from app.schemas import (
    DoctorAvailabilityCreateRequest,
    DoctorAvailabilityResponse,
    DoctorAvailabilityUpdateRequest,
)
from app.services.appointment_client import get_pending_future_appointments

logger = logging.getLogger(__name__)

WEEKDAYS = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
}


def _parse_time(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Time must be formatted as HH:MM.",
        ) from exc


def _parse_date(value: str) -> date:
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date must be formatted as YYYY-MM-DD.",
        ) from exc


def _normalize_day(day: str) -> str:
    normalized = day.strip().lower()
    if normalized not in WEEKDAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"day_of_week must be one of {sorted(WEEKDAYS)}.",
        )
    return normalized


def _validate_availability_window(start_time: str, end_time: str, slot_duration: int) -> None:
    start = _parse_time(start_time)
    end = _parse_time(end_time)
    if start >= end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Availability end_time must be later than start_time.",
        )
    if slot_duration <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="slot_duration must be greater than zero.",
        )
    total_minutes = int((end - start).total_seconds() / 60)
    if total_minutes < slot_duration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="slot_duration must fit within the availability window.",
        )


def _overlaps(
    existing: DoctorAvailability,
    day_of_week: Optional[str],
    date_value: Optional[date],
    start_time: str,
    end_time: str,
    consultation_type: Optional[str],
) -> bool:
    if existing.status != "active":
        return False
    if consultation_type and existing.consultation_type != consultation_type:
        return False
    if existing.date is not None or date_value is not None:
        if existing.date != date_value:
            return False
    else:
        if existing.day_of_week != day_of_week:
            return False
    existing_start = _parse_time(existing.start_time)
    existing_end = _parse_time(existing.end_time)
    candidate_start = _parse_time(start_time)
    candidate_end = _parse_time(end_time)
    return candidate_start < existing_end and existing_start < candidate_end


def _ensure_doctor_exists(db: Session, doctor_id: UUID) -> Doctor:
    doctor = db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
    if doctor.status == "suspended":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Suspended doctors cannot update availability.")
    return doctor


def _ensure_assigned_clinic(db: Session, doctor_id: UUID, clinic_id: UUID) -> None:
    assignment = (
        db.query(DoctorClinicAssignment)
        .filter(
            DoctorClinicAssignment.doctor_id == doctor_id,
            DoctorClinicAssignment.clinic_id == clinic_id,
            DoctorClinicAssignment.status == "active",
        )
        .first()
    )
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctor is not assigned to the requested clinic or clinic assignment is inactive.",
        )


def _normalize_availability_consultation_type(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip().lower()
    allowed = {"physical", "telemedicine"}
    if normalized not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"consultation_type must be one of {sorted(allowed)}.",
        )
    return normalized


def _ensure_no_pending_future_appointments(db: Session, doctor_id: UUID, clinic_id: UUID) -> None:
    pending_count = get_pending_future_appointments(str(doctor_id), str(clinic_id))
    if pending_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot modify or remove availability with pending future appointments.",
        )


def _record_availability_history(
    db: Session,
    availability: DoctorAvailability,
    action: str,
    old_value: dict | None,
    new_value: dict | None,
    changed_by: str | None = None,
) -> None:
    history = DoctorAvailabilityHistory(
        availability_id=availability.availability_id,
        doctor_id=availability.doctor_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        changed_by=changed_by,
    )
    db.add(history)


def create_doctor_availability(
    db: Session,
    doctor_id: UUID,
    payload: DoctorAvailabilityCreateRequest,
) -> DoctorAvailability:
    doctor = _ensure_doctor_exists(db, doctor_id)
    _ensure_assigned_clinic(db, doctor_id, payload.clinic_id)

    day_of_week = None
    date_value = None
    if payload.day_of_week and payload.date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either day_of_week for recurring availability or date for one-time special availability, not both.",
        )
    if payload.day_of_week:
        day_of_week = _normalize_day(payload.day_of_week)
    elif payload.date:
        date_value = _parse_date(payload.date)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either day_of_week or date is required for availability entries.",
        )

    consultation_type = _normalize_availability_consultation_type(payload.consultation_type)
    _validate_availability_window(payload.start_time, payload.end_time, payload.slot_duration)

    existing = (
        db.query(DoctorAvailability)
        .filter(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.clinic_id == payload.clinic_id,
            DoctorAvailability.status == "active",
        )
        .all()
    )
    for candidate in existing:
        if _overlaps(
            candidate,
            day_of_week,
            date_value,
            payload.start_time,
            payload.end_time,
            consultation_type,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="New availability overlaps an existing active availability entry.",
            )

    availability = DoctorAvailability(
        doctor_id=doctor.doctor_id,
        clinic_id=payload.clinic_id,
        day_of_week=day_of_week,
        date=date_value,
        start_time=payload.start_time,
        end_time=payload.end_time,
        slot_duration=payload.slot_duration,
        consultation_type=consultation_type,
        status="active",
    )
    db.add(availability)
    db.commit()
    db.refresh(availability)
    _record_availability_history(
        db,
        availability=availability,
        action="create",
        old_value=None,
        new_value={
            "clinic_id": str(availability.clinic_id),
            "day_of_week": availability.day_of_week,
            "date": availability.date.isoformat() if availability.date else None,
            "start_time": availability.start_time,
            "end_time": availability.end_time,
            "slot_duration": availability.slot_duration,
            "consultation_type": availability.consultation_type,
            "status": availability.status,
        },
        changed_by=None,
    )

    logger.info(
        "Doctor availability created: doctor=%s clinic=%s day=%s date=%s %s-%s",
        doctor.doctor_id,
        availability.clinic_id,
        availability.day_of_week,
        availability.date,
        availability.start_time,
        availability.end_time,
    )
    return availability


def list_doctor_availability(db: Session, doctor_id: UUID) -> list[DoctorAvailabilityResponse]:
    rows = (
        db.query(DoctorAvailability)
        .filter(DoctorAvailability.doctor_id == doctor_id)
        .order_by(DoctorAvailability.date.asc().nullsfirst(), DoctorAvailability.day_of_week.asc().nullsfirst(), DoctorAvailability.start_time.asc())
        .all()
    )
    return [
        DoctorAvailabilityResponse(
            availability_id=row.availability_id,
            clinic_id=row.clinic_id,
            day_of_week=row.day_of_week,
            date=row.date.isoformat() if row.date else None,
            start_time=row.start_time,
            end_time=row.end_time,
            slot_duration=row.slot_duration,
            consultation_type=row.consultation_type,
            status=row.status,
        )
        for row in rows
    ]


def update_doctor_availability(
    db: Session,
    doctor_id: UUID,
    availability_id: UUID,
    payload: DoctorAvailabilityUpdateRequest,
) -> DoctorAvailability:
    doctor = _ensure_doctor_exists(db, doctor_id)
    availability = (
        db.query(DoctorAvailability)
        .filter(
            DoctorAvailability.availability_id == availability_id,
            DoctorAvailability.doctor_id == doctor_id,
        )
        .first()
    )
    if not availability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability entry not found.")

    _ensure_no_pending_future_appointments(db, doctor_id, availability.clinic_id)

    day_of_week = availability.day_of_week
    date_value = availability.date
    if payload.day_of_week and payload.date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either day_of_week or date for availability, not both.",
        )
    if payload.day_of_week is not None:
        day_of_week = _normalize_day(payload.day_of_week)
        date_value = None
    if payload.date is not None:
        date_value = _parse_date(payload.date)
        day_of_week = None

    if payload.start_time is not None or payload.end_time is not None or payload.slot_duration is not None:
        start_time = payload.start_time or availability.start_time
        end_time = payload.end_time or availability.end_time
        slot_duration = payload.slot_duration or availability.slot_duration
        _validate_availability_window(start_time, end_time, slot_duration)
        availability.start_time = start_time
        availability.end_time = end_time
        availability.slot_duration = slot_duration

    old_record = {
        "clinic_id": str(availability.clinic_id),
        "day_of_week": availability.day_of_week,
        "date": availability.date.isoformat() if availability.date else None,
        "start_time": availability.start_time,
        "end_time": availability.end_time,
        "slot_duration": availability.slot_duration,
        "consultation_type": availability.consultation_type,
        "status": availability.status,
    }

    availability.day_of_week = day_of_week
    availability.date = date_value

    if payload.start_time is not None or payload.end_time is not None or payload.slot_duration is not None:
        start_time = payload.start_time or availability.start_time
        end_time = payload.end_time or availability.end_time
        slot_duration = payload.slot_duration or availability.slot_duration
        _validate_availability_window(start_time, end_time, slot_duration)
        availability.start_time = start_time
        availability.end_time = end_time
        availability.slot_duration = slot_duration

    if payload.consultation_type is not None:
        availability.consultation_type = _normalize_availability_consultation_type(payload.consultation_type)

    if payload.status is not None:
        availability.status = payload.status

    new_record = {
        "clinic_id": str(availability.clinic_id),
        "day_of_week": availability.day_of_week,
        "date": availability.date.isoformat() if availability.date else None,
        "start_time": availability.start_time,
        "end_time": availability.end_time,
        "slot_duration": availability.slot_duration,
        "consultation_type": availability.consultation_type,
        "status": availability.status,
    }

    db.add(availability)
    db.commit()
    db.refresh(availability)
    _record_availability_history(
        db,
        availability=availability,
        action="update",
        old_value=old_record,
        new_value=new_record,
        changed_by=None,
    )

    logger.info(
        "Doctor availability updated: doctor=%s availability=%s",
        doctor.doctor_id,
        availability.availability_id,
    )
    return availability


def delete_doctor_availability(db: Session, doctor_id: UUID, availability_id: UUID) -> DoctorAvailability:
    doctor = _ensure_doctor_exists(db, doctor_id)
    availability = (
        db.query(DoctorAvailability)
        .filter(
            DoctorAvailability.availability_id == availability_id,
            DoctorAvailability.doctor_id == doctor_id,
        )
        .first()
    )
    if not availability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability entry not found.")

    _ensure_no_pending_future_appointments(db, doctor_id, availability.clinic_id)

    old_record = {
        "clinic_id": str(availability.clinic_id),
        "day_of_week": availability.day_of_week,
        "date": availability.date.isoformat() if availability.date else None,
        "start_time": availability.start_time,
        "end_time": availability.end_time,
        "slot_duration": availability.slot_duration,
        "consultation_type": availability.consultation_type,
        "status": availability.status,
    }
    availability.status = "inactive"
    db.add(availability)
    db.commit()
    db.refresh(availability)
    _record_availability_history(
        db,
        availability=availability,
        action="delete",
        old_value=old_record,
        new_value={"status": "inactive"},
        changed_by=None,
    )

    logger.info(
        "Doctor availability deactivated: doctor=%s availability=%s",
        doctor.doctor_id,
        availability.availability_id,
    )
    return availability
