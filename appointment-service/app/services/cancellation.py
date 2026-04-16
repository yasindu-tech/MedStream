"""Cancellation logic implementing distinct workflows across different JWT roles."""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Appointment, AppointmentStatusHistory, Patient
from app.schemas import CancelAppointmentRequest
from app.services.followup import _get_doctor_info_by_user


def cancel_appointment(
    db: Session,
    *,
    user: dict,
    appointment_id: UUID,
    request: CancelAppointmentRequest,
) -> dict:
    """
    Orchestrate cancellation logic switching precisely on the incoming requestor's role.
    """
    appt = db.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")

    # 1. Broad Idempotency & Edge Case filtering
    if appt.status == "cancelled":
        return {
            "appointment_id": str(appt.appointment_id),
            "status": appt.status,
            "message": "Appointment is already cancelled."
        }

    if appt.status in ["completed", "in_progress"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointment cannot be cancelled because it is presently '{appt.status}'."
        )

    role = user.get("role")
    if not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing role claim in token.")

    user_sub = user.get("sub")
    if not user_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing subject claim in token.")
    try:
        user_id = UUID(str(user_sub))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid subject claim in token.")
    
    # 2. Branch workflows by Role
    if role == "patient":
        _handle_patient_cancel(db, appt, user_id, request.reason)
    elif role == "doctor":
        _handle_doctor_cancel(db, appt, user_id, request.reason)
    elif role == "admin":
        _handle_admin_cancel(appt, user_id, request.reason)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unrecognized role for cancellation action.")

    # 3. Handle Auditing Trace
    # Regardless of which exact sub-service threw exceptions or bound the model, apply changes here transactionally.
    history_record = AppointmentStatusHistory(
        appointment_id=appt.appointment_id,
        old_status=appt.status,
        new_status="cancelled",
        changed_by=f"Role: {role} (ID: {str(user_id)})",
        reason=request.reason or "No reason provided"
    )
    db.add(history_record)

    appt.status = "cancelled"
    appt.cancelled_by = role
    appt.cancellation_reason = request.reason

    db.commit()
    db.refresh(appt)

    # 4. Trigger Webhooks for Notifications / Refunds
    # TODO: if `appt.payment_status` != "pending", notify `payment-service` to process refund requests depending on Cutoffs.
    # TODO: notify `notification-service`.

    return {
        "appointment_id": str(appt.appointment_id),
        "status": appt.status,
        "message": f"Appointment successfully cancelled by {role}."
    }


def _handle_patient_cancel(db: Session, appt: Appointment, user_id: UUID, reason: Optional[str]):
    patient = db.query(Patient).filter(Patient.user_id == user_id).first()
    if not patient or appt.patient_id != patient.patient_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only cancel your own appointments.")

    # Apply configuration boundaries
    appt_dt = datetime.combine(appt.appointment_date, appt.start_time)
    now_dt = datetime.now() 
    if (appt_dt - now_dt) < timedelta(hours=settings.CANCELLATION_WINDOW_HOURS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Patients can only cancel directly up to {settings.CANCELLATION_WINDOW_HOURS} hours before the appointment."
        )

def _handle_doctor_cancel(db: Session, appt: Appointment, user_id: UUID, reason: Optional[str]):
    # Prevent doctors throwing away requests quietly
    if not reason or len(reason.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctors are required to supply a valid operational reason for cancelling an appointment."
        )

    doctor_info = _get_doctor_info_by_user(str(user_id))
    if UUID(doctor_info["doctor_id"]) != appt.doctor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are restricted to cancelling your own appointments exclusively.")

def _handle_admin_cancel(appt: Appointment, user_id: UUID, reason: Optional[str]):
    # Absolute override capability. Admins can cancel universally.
    pass
