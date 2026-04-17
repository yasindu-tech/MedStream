"""Appointment outcome workflows for completed/no-show/arrived states."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Appointment, AppointmentStatusHistory, Patient
from app.services.followup import _get_doctor_info_by_user
from app.services.policy import resolve_policy_for_appointment


TERMINAL_STATUSES = {"completed", "cancelled", "no_show", "technical_failed"}


def mark_arrived(
    db: Session,
    *,
    appointment_id: UUID,
    actor_role: str,
    actor_user_id: str,
    reason: str | None,
) -> Appointment:
    appt = _load_appointment(db, appointment_id)
    _reject_if_cancelled_or_terminal(appt)
    if appt.status == "arrived":
        return appt

    _record_history(
        db,
        appointment_id=appt.appointment_id,
        old_status=appt.status,
        new_status="arrived",
        changed_by=f"Role: {actor_role} (ID: {actor_user_id})",
        reason=reason or "Patient marked as arrived",
    )
    appt.status = "arrived"
    db.commit()
    db.refresh(appt)
    _emit_notification_event(
        db,
        event_type="appointment.arrived",
        appointment=appt,
        actor_role=actor_role,
        actor_user_id=actor_user_id,
    )
    return appt


def mark_completed(
    db: Session,
    *,
    appointment_id: UUID,
    actor_role: str,
    actor_user_id: str,
    reason: str | None = None,
) -> Appointment:
    appt = _load_appointment(db, appointment_id)
    _reject_if_cancelled_or_terminal(appt)

    if appt.status not in {"confirmed", "in_progress", "arrived"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot mark appointment as completed from '{appt.status}' status",
        )

    if actor_role == "doctor":
        doctor_info = _get_doctor_info_by_user(actor_user_id)
        if UUID(doctor_info["doctor_id"]) != appt.doctor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only complete your own appointments")

    now_dt = datetime.now()
    appt_dt = datetime.combine(appt.appointment_date, appt.start_time)
    if now_dt < appt_dt and actor_role not in {"admin", "staff"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot mark appointment as completed before scheduled time",
        )

    _record_history(
        db,
        appointment_id=appt.appointment_id,
        old_status=appt.status,
        new_status="completed",
        changed_by=f"Role: {actor_role} (ID: {actor_user_id})",
        reason=reason or "Consultation completed",
    )
    appt.status = "completed"
    appt.completed_at = now_dt
    appt.completed_by = f"{actor_role}:{actor_user_id}"

    db.commit()
    db.refresh(appt)
    _emit_notification_event(
        db,
        event_type="appointment.completed",
        appointment=appt,
        actor_role=actor_role,
        actor_user_id=actor_user_id,
    )
    _trigger_post_completion_workflows(
        db,
        appointment=appt,
        actor_role=actor_role,
        actor_user_id=actor_user_id,
    )
    return appt


def mark_no_show(
    db: Session,
    *,
    appointment_id: UUID,
    actor_role: str,
    actor_user_id: str,
    reason: str | None,
    observed_join_within_grace: bool = False,
) -> Appointment:
    appt = _load_appointment(db, appointment_id)
    _reject_if_cancelled_or_terminal(appt)

    if observed_join_within_grace:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Patient joined during grace period; no-show cannot be marked")

    if actor_role == "system" and appt.appointment_type != "telemedicine":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System no-show automation is only supported for telemedicine appointments",
        )

    policy = resolve_policy_for_appointment(db, appt.policy_id)
    now_dt = datetime.now()
    appt_dt = datetime.combine(appt.appointment_date, appt.start_time)
    grace_deadline = appt_dt.timestamp() + (policy.no_show_grace_period_minutes * 60)
    if now_dt.timestamp() < grace_deadline and actor_role not in {"admin", "staff"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No-show grace period has not elapsed yet",
        )

    _record_history(
        db,
        appointment_id=appt.appointment_id,
        old_status=appt.status,
        new_status="no_show",
        changed_by=f"Role: {actor_role} (ID: {actor_user_id})",
        reason=reason or "No-show recorded",
    )
    appt.status = "no_show"
    appt.no_show_at = now_dt
    appt.no_show_marked_by = f"{actor_role}:{actor_user_id}"

    db.commit()
    db.refresh(appt)
    _emit_notification_event(
        db,
        event_type="appointment.no_show",
        appointment=appt,
        actor_role=actor_role,
        actor_user_id=actor_user_id,
    )
    return appt


def mark_technical_failure(
    db: Session,
    *,
    appointment_id: UUID,
    actor_role: str,
    actor_user_id: str,
    reason: str | None,
) -> Appointment:
    appt = _load_appointment(db, appointment_id)
    _reject_if_cancelled_or_terminal(appt)

    if actor_role == "doctor":
        doctor_info = _get_doctor_info_by_user(actor_user_id)
        if UUID(doctor_info["doctor_id"]) != appt.doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only mark technical failure for your own appointments",
            )

    if actor_role == "patient":
        patient = db.query(Patient).filter(Patient.user_id == UUID(actor_user_id)).first()
        if not patient or patient.patient_id != appt.patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only mark technical failure for your own appointment",
            )

    if actor_role == "system" and appt.appointment_type != "telemedicine":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System technical-failure automation is only supported for telemedicine appointments",
        )

    now_dt = datetime.now()
    technical_reason = reason or "Technical issue reported during consultation"

    _record_history(
        db,
        appointment_id=appt.appointment_id,
        old_status=appt.status,
        new_status="technical_failed",
        changed_by=f"Role: {actor_role} (ID: {actor_user_id})",
        reason=technical_reason,
    )
    appt.status = "technical_failed"
    appt.technical_failure_at = now_dt
    appt.technical_failure_reason = technical_reason
    appt.technical_failure_marked_by = f"{actor_role}:{actor_user_id}"

    db.commit()
    db.refresh(appt)

    _emit_notification_event(
        db,
        event_type="appointment.technical_failure",
        appointment=appt,
        actor_role=actor_role,
        actor_user_id=actor_user_id,
    )
    _trigger_reschedule_recommendation(
        db,
        appointment=appt,
        actor_role=actor_role,
        actor_user_id=actor_user_id,
        reason=technical_reason,
    )
    return appt


def _load_appointment(db: Session, appointment_id: UUID) -> Appointment:
    appt = db.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return appt


def _reject_if_cancelled_or_terminal(appt: Appointment) -> None:
    if appt.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot update outcome for a cancelled appointment")
    if appt.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Appointment is already in terminal state '{appt.status}'")


def _record_history(
    db: Session,
    *,
    appointment_id: UUID,
    old_status: str | None,
    new_status: str,
    changed_by: str,
    reason: str,
) -> None:
    db.add(
        AppointmentStatusHistory(
            appointment_id=appointment_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            reason=reason,
        )
    )


def _emit_notification_event(
    db: Session,
    *,
    event_type: str,
    appointment: Appointment,
    actor_role: str,
    actor_user_id: str,
) -> None:
    patient_user_id = _resolve_patient_user_id(db, appointment.patient_id)
    if not patient_user_id:
        return

    payload = {
        "event_type": event_type,
        "user_id": patient_user_id,
        "payload": {
            "appointment_id": str(appointment.appointment_id),
            "status": appointment.status,
            "clinic_name": appointment.clinic_name,
            "doctor_name": appointment.doctor_name,
            "date": appointment.appointment_date.isoformat(),
            "start_time": appointment.start_time.strftime("%H:%M"),
            "actor_role": actor_role,
            "actor_user_id": actor_user_id,
        },
        "channels": ["in_app"],
        "priority": "normal",
    }

    try:
        with httpx.Client(timeout=2.0) as client:
            client.post(f"{settings.NOTIFICATION_SERVICE_URL}/api/notifications/events", json=payload)
    except httpx.RequestError:
        # Fail-open for non-critical notification calls.
        return


def _trigger_post_completion_workflows(
    db: Session,
    *,
    appointment: Appointment,
    actor_role: str,
    actor_user_id: str,
) -> None:
    """
    Emit workflow trigger events so downstream services can start
    prescription and follow-up handling after completion.
    """
    _emit_notification_event(
        db,
        event_type="workflow.prescription.trigger",
        appointment=appointment,
        actor_role=actor_role,
        actor_user_id=actor_user_id,
    )
    _emit_notification_event(
        db,
        event_type="workflow.followup.trigger",
        appointment=appointment,
        actor_role=actor_role,
        actor_user_id=actor_user_id,
    )


def _trigger_reschedule_recommendation(
    db: Session,
    *,
    appointment: Appointment,
    actor_role: str,
    actor_user_id: str,
    reason: str,
) -> None:
    patient_user_id = _resolve_patient_user_id(db, appointment.patient_id)
    if not patient_user_id:
        return

    payload = {
        "event_type": "workflow.reschedule.recommendation",
        "user_id": patient_user_id,
        "payload": {
            "appointment_id": str(appointment.appointment_id),
            "status": appointment.status,
            "technical_failure_reason": reason,
            "clinic_name": appointment.clinic_name,
            "doctor_name": appointment.doctor_name,
            "date": appointment.appointment_date.isoformat(),
            "start_time": appointment.start_time.strftime("%H:%M"),
            "actor_role": actor_role,
            "actor_user_id": actor_user_id,
            "recommend_reschedule": True,
        },
        "channels": ["in_app"],
        "priority": "high",
    }

    try:
        with httpx.Client(timeout=2.0) as client:
            client.post(f"{settings.NOTIFICATION_SERVICE_URL}/api/notifications/events", json=payload)
    except httpx.RequestError:
        return


def _resolve_patient_user_id(db: Session, patient_id: UUID) -> str | None:
    patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
    if not patient or not patient.user_id:
        return None
    return str(patient.user_id)
