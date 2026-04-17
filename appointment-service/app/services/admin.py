"""Admin and clinic-staff appointment management services."""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models import Appointment, AppointmentStatusHistory, Patient, TelemedicineSession
from app.schemas import (
    AppointmentListItemResponse,
    AppointmentListPaginatedResponse,
    AppointmentStatsResponse,
    TelemedicineLiveStatusItem,
    TelemedicineLiveStatusPaginatedResponse,
)
from app.services.clinic_scope import resolve_staff_clinic_id


def list_appointments_for_admin(
    db: Session,
    *,
    user: dict,
    page: int,
    size: int,
    patient_id: Optional[UUID],
    doctor_id: Optional[UUID],
    clinic_id: Optional[UUID],
    patient_name: Optional[str],
    doctor_name: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
    status: Optional[str],
) -> AppointmentListPaginatedResponse:
    query = db.query(Appointment, Patient).join(Patient, Appointment.patient_id == Patient.patient_id)

    role = user.get("role")
    user_id = user.get("sub")
    if role == "staff":
        scoped_clinic_id = resolve_staff_clinic_id(user_id)
        query = query.filter(Appointment.clinic_id == scoped_clinic_id)
    elif role != "admin":
        raise ValueError("Invalid role for admin listing")

    if patient_id:
        query = query.filter(Appointment.patient_id == patient_id)
    if doctor_id:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if patient_name:
        query = query.filter(Patient.full_name.ilike(f"%{patient_name}%"))
    if doctor_name:
        query = query.filter(Appointment.doctor_name.ilike(f"%{doctor_name}%"))
    if clinic_id and role == "admin":
        query = query.filter(Appointment.clinic_id == clinic_id)
    if date_from:
        query = query.filter(Appointment.appointment_date >= date_from)
    if date_to:
        query = query.filter(Appointment.appointment_date <= date_to)
    if status:
        query = query.filter(Appointment.status == status)

    query = query.order_by(desc(Appointment.appointment_date), desc(Appointment.start_time))
    total = query.count()
    offset = (page - 1) * size
    rows = query.offset(offset).limit(size).all()

    items = [
        AppointmentListItemResponse(
            appointment_id=appt.appointment_id,
            doctor_id=appt.doctor_id or UUID(int=0),
            doctor_name=appt.doctor_name,
            clinic_id=appt.clinic_id or UUID(int=0),
            clinic_name=appt.clinic_name,
            patient_id=appt.patient_id,
            patient_name=pat.full_name,
            date=appt.appointment_date,
            start_time=appt.start_time.strftime("%H:%M"),
            end_time=appt.end_time.strftime("%H:%M"),
            status=appt.status,
            payment_status=appt.payment_status,
            consultation_type=appt.appointment_type,
        )
        for appt, pat in rows
    ]

    return AppointmentListPaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        has_more=(offset + len(items)) < total,
    )


def get_status_history_for_admin(
    db: Session,
    *,
    appointment_id: UUID,
    user: dict,
) -> list[AppointmentStatusHistory]:
    appt = db.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    role = user.get("role")
    if role == "staff":
        scoped_clinic_id = resolve_staff_clinic_id(user.get("sub"))
        if appt.clinic_id != scoped_clinic_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied for appointment outside your clinic")

    return (
        db.query(AppointmentStatusHistory)
        .filter(AppointmentStatusHistory.appointment_id == appointment_id)
        .order_by(AppointmentStatusHistory.changed_at.asc())
        .all()
    )


def get_appointment_stats(
    db: Session,
    *,
    user: dict,
    date_from: Optional[date],
    date_to: Optional[date],
    clinic_id: Optional[UUID],
    doctor_id: Optional[UUID],
    outcome: Optional[str],
) -> AppointmentStatsResponse:
    query = db.query(Appointment)

    role = user.get("role")
    if role == "staff":
        scoped_clinic_id = resolve_staff_clinic_id(user.get("sub"))
        query = query.filter(Appointment.clinic_id == scoped_clinic_id)
        if clinic_id and clinic_id != scoped_clinic_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff can only query stats for their own clinic")
    elif role == "admin" and clinic_id:
        query = query.filter(Appointment.clinic_id == clinic_id)

    if date_from:
        query = query.filter(Appointment.appointment_date >= date_from)
    if date_to:
        query = query.filter(Appointment.appointment_date <= date_to)
    if doctor_id:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if outcome:
        query = query.filter(Appointment.status == outcome)

    total = query.count()
    cancelled = query.filter(Appointment.status == "cancelled").count()
    no_show = query.filter(Appointment.status == "no_show").count()
    completed = query.filter(Appointment.status == "completed").count()
    technical_failed = query.filter(Appointment.status == "technical_failed").count()

    duration_query = (
        db.query(
            func.avg(
                func.extract("epoch", TelemedicineSession.ended_at - TelemedicineSession.started_at) / 60.0
            )
        )
        .join(Appointment, Appointment.appointment_id == TelemedicineSession.appointment_id)
        .filter(Appointment.appointment_type == "telemedicine")
        .filter(TelemedicineSession.started_at.isnot(None), TelemedicineSession.ended_at.isnot(None))
    )
    if role == "staff":
        duration_query = duration_query.filter(Appointment.clinic_id == resolve_staff_clinic_id(user.get("sub")))
    elif role == "admin" and clinic_id:
        duration_query = duration_query.filter(Appointment.clinic_id == clinic_id)
    if date_from:
        duration_query = duration_query.filter(Appointment.appointment_date >= date_from)
    if date_to:
        duration_query = duration_query.filter(Appointment.appointment_date <= date_to)
    if doctor_id:
        duration_query = duration_query.filter(Appointment.doctor_id == doctor_id)
    if outcome:
        duration_query = duration_query.filter(Appointment.status == outcome)

    avg_duration = duration_query.scalar()

    return AppointmentStatsResponse(
        total_bookings=total,
        total_cancellations=cancelled,
        total_no_shows=no_show,
        total_completed=completed,
        total_failed_sessions=technical_failed,
        average_duration_minutes=round(float(avg_duration), 2) if avg_duration is not None else None,
    )


def get_live_telemedicine_statuses(
    db: Session,
    *,
    user: dict,
    page: int,
    size: int,
    clinic_id: Optional[UUID],
    doctor_id: Optional[UUID],
    date_from: Optional[date],
    date_to: Optional[date],
    outcome: Optional[str],
) -> TelemedicineLiveStatusPaginatedResponse:
    query = (
        db.query(TelemedicineSession, Appointment, Patient)
        .join(Appointment, Appointment.appointment_id == TelemedicineSession.appointment_id)
        .join(Patient, Patient.patient_id == Appointment.patient_id)
        .filter(Appointment.appointment_type == "telemedicine")
    )

    role = user.get("role")
    if role == "staff":
        scoped_clinic_id = resolve_staff_clinic_id(user.get("sub"))
        query = query.filter(Appointment.clinic_id == scoped_clinic_id)
        if clinic_id and clinic_id != scoped_clinic_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff can only view live statuses for their own clinic")
    elif role == "admin" and clinic_id:
        query = query.filter(Appointment.clinic_id == clinic_id)

    if doctor_id:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if date_from:
        query = query.filter(Appointment.appointment_date >= date_from)
    if date_to:
        query = query.filter(Appointment.appointment_date <= date_to)
    if outcome:
        query = query.filter(Appointment.status == outcome)

    query = query.order_by(desc(Appointment.appointment_date), desc(Appointment.start_time))
    total = query.count()
    offset = (page - 1) * size
    rows = query.offset(offset).limit(size).all()

    items: list[TelemedicineLiveStatusItem] = []
    for session, appointment, patient in rows:
        duration_minutes = None
        if session.started_at and session.ended_at:
            duration_minutes = round((session.ended_at - session.started_at).total_seconds() / 60.0, 2)
        items.append(
            TelemedicineLiveStatusItem(
                session_id=session.session_id,
                appointment_id=appointment.appointment_id,
                doctor_id=appointment.doctor_id,
                doctor_name=appointment.doctor_name,
                clinic_id=appointment.clinic_id,
                clinic_name=appointment.clinic_name,
                patient_id=appointment.patient_id,
                patient_name=patient.full_name,
                appointment_date=appointment.appointment_date,
                start_time=appointment.start_time.strftime("%H:%M"),
                end_time=appointment.end_time.strftime("%H:%M"),
                appointment_status=appointment.status,
                session_status=session.status,
                provider_name=session.provider_name,
                duration_minutes=duration_minutes,
                started_at=session.started_at.isoformat() if session.started_at else None,
                ended_at=session.ended_at.isoformat() if session.ended_at else None,
            )
        )

    return TelemedicineLiveStatusPaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        has_more=(offset + len(items)) < total,
    )
