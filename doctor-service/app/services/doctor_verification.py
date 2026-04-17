from __future__ import annotations
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Doctor
from app.services.notification_client import send_notification_event


def list_pending_doctors(db: Session) -> list[Doctor]:
    return (
        db.query(Doctor)
        .filter(Doctor.verification_status == "pending")
        .order_by(Doctor.created_at.asc())
        .all()
    )


def get_doctor_verification_documents(db: Session, doctor_id: UUID) -> Doctor | None:
    return db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()


def _ensure_doctor_exists(db: Session, doctor_id: UUID) -> Doctor:
    doctor = db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
    return doctor


def review_doctor_verification(
    db: Session,
    doctor_id: UUID,
    action: str,
    reviewer_id: str | None = None,
    reason: str | None = None,
) -> Doctor:
    doctor = _ensure_doctor_exists(db, doctor_id)

    if doctor.verification_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor verification can only be reviewed when status is pending.",
        )

    if action not in ("approve", "reject"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be 'approve' or 'reject'.",
        )

    if action == "approve" and not doctor.verification_documents:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot approve verification without submitted documents.",
        )

    if action == "approve":
        if doctor.medical_registration_no:
            duplicate = (
                db.query(Doctor)
                .filter(
                    Doctor.doctor_id != doctor.doctor_id,
                    Doctor.medical_registration_no == doctor.medical_registration_no,
                )
                .first()
            )
            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Duplicate medical registration number detected.",
                )

        doctor.verification_status = "verified"
        doctor.verification_rejection_reason = None
        doctor.status = "active"
        notification_event = "doctor.verification.approved"
        notification_payload: dict[str, Any] = {
            "doctor_name": doctor.full_name,
            "reason": reason or "Your documents have been approved.",
        }
    else:
        doctor.verification_status = "rejected"
        doctor.verification_rejection_reason = reason or "Verification rejected by administrator."
        notification_event = "doctor.verification.rejected"
        notification_payload = {
            "doctor_name": doctor.full_name,
            "reason": doctor.verification_rejection_reason,
        }

    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    if doctor.user_id:
        send_notification_event(
            event_type=notification_event,
            user_id=str(doctor.user_id),
            payload=notification_payload,
        )

    return doctor


def suspend_doctor_profile(db: Session, doctor_id: UUID, reason: str | None = None) -> Doctor:
    doctor = _ensure_doctor_exists(db, doctor_id)
    if doctor.status == "suspended":
        return doctor

    doctor.status = "suspended"
    doctor.suspension_reason = reason
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor
