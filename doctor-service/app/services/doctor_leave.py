from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Doctor, DoctorLeave
from app.schemas import DoctorLeaveRequest, DoctorLeaveResponse
from app.services.appointment_client import get_pending_future_appointments


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Datetime must be ISO 8601 format (YYYY-MM-DDTHH:MM:SS).",
        ) from exc


def _ensure_active_doctor(db: Session, doctor_id: UUID) -> Doctor:
    doctor = db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
    if doctor.status == "suspended":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Suspended doctors cannot create leave blocks.")
    return doctor


def create_doctor_leave(db: Session, doctor_id: UUID, payload: DoctorLeaveRequest) -> DoctorLeave:
    doctor = _ensure_active_doctor(db, doctor_id)
    start_datetime = _parse_datetime(payload.start_datetime)
    end_datetime = _parse_datetime(payload.end_datetime)

    if start_datetime >= end_datetime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Leave end_datetime must be after start_datetime.",
        )

    if payload.clinic_id:
        pending = get_pending_future_appointments(str(doctor_id), str(payload.clinic_id))
    else:
        pending = get_pending_future_appointments(str(doctor_id))
    if pending > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot create leave while there are pending or confirmed future appointments.",
        )

    leave = DoctorLeave(
        doctor_id=doctor.doctor_id,
        clinic_id=payload.clinic_id,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        reason=payload.reason,
        status="active",
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)

    return leave


def list_doctor_leaves(db: Session, doctor_id: UUID) -> List[DoctorLeaveResponse]:
    leaves = (
        db.query(DoctorLeave)
        .filter(DoctorLeave.doctor_id == doctor_id)
        .order_by(DoctorLeave.start_datetime.asc())
        .all()
    )
    return [
        DoctorLeaveResponse(
            leave_id=leave.leave_id,
            clinic_id=leave.clinic_id,
            start_datetime=leave.start_datetime.isoformat(),
            end_datetime=leave.end_datetime.isoformat(),
            reason=leave.reason,
            status=leave.status,
        )
        for leave in leaves
    ]


def delete_doctor_leave(db: Session, doctor_id: UUID, leave_id: UUID) -> DoctorLeave:
    leave = (
        db.query(DoctorLeave)
        .filter(DoctorLeave.leave_id == leave_id, DoctorLeave.doctor_id == doctor_id)
        .first()
    )
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave entry not found.")

    leave.status = "inactive"
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave
