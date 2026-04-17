"""Consultation workflows: doctor approval, notes, prescriptions, and patient summary."""
from __future__ import annotations
from datetime import datetime
from typing import Any, List
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Appointment,
    AppointmentNote,
    AppointmentStatusHistory,
    Patient,
    Prescription,
    PatientDocument,
)
from app.schemas import PrescriptionRequest
from app.services.followup import _get_doctor_info_by_user


def _emit_notification_event(event_type: str, user_id: str, payload: dict[str, Any]) -> None:
    try:
        with httpx.Client(timeout=2.0) as client:
            client.post(
                f"{settings.NOTIFICATION_SERVICE_URL}/api/notifications/events",
                json={
                    "event_type": event_type,
                    "user_id": user_id,
                    "payload": payload,
                    "channels": ["in_app"],
                    "priority": "normal",
                },
            )
    except httpx.RequestError:
        return


def _resolve_patient_user_id(db: Session, patient_id: UUID) -> str | None:
    patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
    if not patient or not patient.user_id:
        return None
    return str(patient.user_id)


def _resolve_doctor_id(user_id: str) -> tuple[UUID, str]:
    doctor_info = _get_doctor_info_by_user(user_id)
    return UUID(doctor_info["doctor_id"]), doctor_info["full_name"]


def _load_appointment(db: Session, appointment_id: UUID) -> Appointment:
    appt = db.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    return appt


def _ensure_doctor_owns_appointment(db: Session, appointment_id: UUID, doctor_user_id: str) -> Appointment:
    appt = _load_appointment(db, appointment_id)
    doctor_id, _ = _resolve_doctor_id(doctor_user_id)
    if appt.doctor_id != doctor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only manage your own appointments.")
    return appt


def _record_appointment_history(db: Session, appt: Appointment, old_status: str | None, new_status: str, reason: str | None) -> None:
    history = AppointmentStatusHistory(
        appointment_id=appt.appointment_id,
        old_status=old_status,
        new_status=new_status,
        changed_by="doctor",
        reason=reason or "Doctor action",
    )
    db.add(history)


def doctor_accept_appointment(db: Session, appointment_id: UUID, doctor_user_id: str) -> Appointment:
    appt = _ensure_doctor_owns_appointment(db, appointment_id, doctor_user_id)
    if appt.status in {"cancelled", "completed", "in_progress", "arrived"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointment cannot be accepted from status '{appt.status}'.",
        )

    old_status = appt.status
    if appt.payment_status == "pending":
        appt.status = "pending_payment"
    else:
        appt.status = "confirmed"

    if old_status != appt.status:
        _record_appointment_history(db, appt, old_status, appt.status, "Doctor accepted the appointment")

    db.add(appt)
    db.commit()
    db.refresh(appt)

    patient_user_id = _resolve_patient_user_id(db, appt.patient_id)
    if patient_user_id:
        _emit_notification_event(
            event_type="appointment.accepted",
            user_id=patient_user_id,
            payload={
                "appointment_id": str(appt.appointment_id),
                "status": appt.status,
                "doctor_name": str(appt.doctor_name),
                "clinic_name": str(appt.clinic_name),
                "date": appt.appointment_date.isoformat(),
                "start_time": appt.start_time.strftime("%H:%M"),
            },
        )

    return appt


def doctor_reject_appointment(db: Session, appointment_id: UUID, doctor_user_id: str, reason: str | None) -> Appointment:
    appt = _ensure_doctor_owns_appointment(db, appointment_id, doctor_user_id)
    if appt.status in {"cancelled", "completed", "in_progress", "arrived"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointment cannot be rejected from status '{appt.status}'.",
        )

    if not reason or not reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection reason is required.",
        )

    old_status = appt.status
    appt.status = "cancelled"
    appt.cancellation_reason = reason
    appt.cancelled_by = "doctor"
    _record_appointment_history(db, appt, old_status, appt.status, reason)

    db.add(appt)
    db.commit()
    db.refresh(appt)

    patient_user_id = _resolve_patient_user_id(db, appt.patient_id)
    if patient_user_id:
        _emit_notification_event(
            event_type="appointment.rejected",
            user_id=patient_user_id,
            payload={
                "appointment_id": str(appt.appointment_id),
                "status": appt.status,
                "reason": reason,
                "doctor_name": str(appt.doctor_name),
            },
        )

    return appt


def create_appointment_note(db: Session, appointment_id: UUID, doctor_user_id: str, content: str) -> AppointmentNote:
    appt = _ensure_doctor_owns_appointment(db, appointment_id, doctor_user_id)
    if appt.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot add notes to a cancelled appointment.")

    note = AppointmentNote(
        appointment_id=appt.appointment_id,
        doctor_id=appt.doctor_id,
        content=content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_appointment_notes(db: Session, appointment_id: UUID, doctor_user_id: str) -> list[AppointmentNote]:
    appt = _ensure_doctor_owns_appointment(db, appointment_id, doctor_user_id)
    return (
        db.query(AppointmentNote)
        .filter(AppointmentNote.appointment_id == appt.appointment_id)
        .order_by(AppointmentNote.created_at.asc())
        .all()
    )


def create_patient_document(db: Session, appointment_id: UUID, doctor_user_id: str, request: "PatientDocumentRequest") -> PatientDocument:
    appt = _ensure_doctor_owns_appointment(db, appointment_id, doctor_user_id)
    document = PatientDocument(
        patient_id=appt.patient_id,
        appointment_id=appt.appointment_id,
        name=request.name,
        document_type=request.document_type,
        url=request.url,
        description=request.description,
        uploaded_by=doctor_user_id,
        visibility="doctor_only",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def create_prescription(db: Session, appointment_id: UUID, doctor_user_id: str, request: PrescriptionRequest) -> Prescription:
    appt = _ensure_doctor_owns_appointment(db, appointment_id, doctor_user_id)
    if appt.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create a prescription for a cancelled appointment.")
    if not request.medications:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one medication item is required for a prescription.")

    existing_prescription = (
        db.query(Prescription)
        .filter(Prescription.appointment_id == appt.appointment_id)
        .first()
    )
    if existing_prescription:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A prescription already exists for this appointment. Update the existing draft or finalize it.",
        )

    prescription = Prescription(
        appointment_id=appt.appointment_id,
        doctor_id=appt.doctor_id,
        patient_id=appt.patient_id,
        clinic_id=appt.clinic_id,
        medications=[item.model_dump(exclude_none=True) for item in request.medications],
        instructions=request.instructions,
        status="draft",
    )
    db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return prescription


def update_prescription(db: Session, appointment_id: UUID, prescription_id: UUID, doctor_user_id: str, request: PrescriptionRequest) -> Prescription:
    appt = _ensure_doctor_owns_appointment(db, appointment_id, doctor_user_id)
    prescription = (
        db.query(Prescription)
        .filter(Prescription.prescription_id == prescription_id, Prescription.appointment_id == appt.appointment_id)
        .first()
    )
    if not prescription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found.")
    if prescription.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft prescriptions can be updated.")

    prescription.medications = [item.model_dump(exclude_none=True) for item in request.medications]
    prescription.instructions = request.instructions
    db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return prescription


def finalize_prescription(db: Session, appointment_id: UUID, prescription_id: UUID, doctor_user_id: str) -> Prescription:
    appt = _ensure_doctor_owns_appointment(db, appointment_id, doctor_user_id)
    prescription = (
        db.query(Prescription)
        .filter(Prescription.prescription_id == prescription_id, Prescription.appointment_id == appt.appointment_id)
        .first()
    )
    if not prescription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found.")
    if prescription.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft prescriptions can be finalized.")

    now = datetime.now()
    prescription.status = "final"
    prescription.issued_at = now
    prescription.finalized_at = now
    db.add(prescription)
    db.commit()
    db.refresh(prescription)

    patient = db.query(Patient).filter(Patient.patient_id == appt.patient_id).first()
    if patient and patient.user_id:
        _emit_notification_event(
            event_type="prescription.available",
            user_id=str(patient.user_id),
            payload={
                "appointment_id": str(appt.appointment_id),
                "prescription_id": str(prescription.prescription_id),
                "doctor_name": str(appt.doctor_name),
                "clinic_name": str(appt.clinic_name),
                "date": appt.appointment_date.isoformat(),
            },
        )
    return prescription


def list_prescriptions(db: Session, appointment_id: UUID, doctor_user_id: str) -> list[Prescription]:
    appt = _ensure_doctor_owns_appointment(db, appointment_id, doctor_user_id)
    return (
        db.query(Prescription)
        .filter(Prescription.appointment_id == appt.appointment_id)
        .order_by(Prescription.created_at.asc())
        .all()
    )


def get_patient_summary(db: Session, appointment_id: UUID, doctor_user_id: str) -> dict[str, Any]:
    appt = _ensure_doctor_owns_appointment(db, appointment_id, doctor_user_id)
    patient = db.query(Patient).filter(Patient.patient_id == appt.patient_id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found.")

    return {
        "patient_id": patient.patient_id,
        "full_name": patient.full_name,
        "dob": patient.dob,
        "gender": patient.gender,
        "nic_passport": patient.nic_passport,
        "phone": patient.phone,
        "address": patient.address,
        "blood_group": patient.blood_group,
        "appointment_id": appt.appointment_id,
        "appointment_date": appt.appointment_date,
        "appointment_start_time": appt.start_time.strftime("%H:%M"),
        "appointment_end_time": appt.end_time.strftime("%H:%M"),
        "appointment_type": appt.appointment_type,
        "appointment_status": appt.status,
        "consultation_fee": None,
    }


def list_patient_documents(db: Session, appointment_id: UUID, doctor_user_id: str) -> list[PatientDocument]:
    appt = _ensure_doctor_owns_appointment(db, appointment_id, doctor_user_id)
    return (
        db.query(PatientDocument)
        .filter(
            PatientDocument.patient_id == appt.patient_id,
            (PatientDocument.appointment_id == appt.appointment_id) | (PatientDocument.appointment_id.is_(None))
        )
        .order_by(PatientDocument.uploaded_at.desc())
        .all()
    )
