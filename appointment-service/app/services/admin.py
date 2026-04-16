"""Super admin and clinic admin appointment management services."""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import Appointment, AppointmentStatusHistory, Patient
from app.schemas import AppointmentListItemResponse, AppointmentListPaginatedResponse, AppointmentStatsResponse
from app.services.clinic_scope import resolve_clinic_admin_clinic_id


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
    if role == "clinic_admin":
        scoped_clinic_id = resolve_clinic_admin_clinic_id(user_id)
        query = query.filter(Appointment.clinic_id == scoped_clinic_id)
    elif role != "super_admin":
        raise ValueError("Invalid role for admin listing")

    if patient_id:
        query = query.filter(Appointment.patient_id == patient_id)
    if doctor_id:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if patient_name:
        query = query.filter(Patient.full_name.ilike(f"%{patient_name}%"))
    if doctor_name:
        query = query.filter(Appointment.doctor_name.ilike(f"%{doctor_name}%"))
    if clinic_id and role == "super_admin":
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
    if role == "clinic_admin":
        scoped_clinic_id = resolve_clinic_admin_clinic_id(user.get("sub"))
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
) -> AppointmentStatsResponse:
    query = db.query(Appointment)

    role = user.get("role")
    if role == "clinic_admin":
        query = query.filter(Appointment.clinic_id == resolve_clinic_admin_clinic_id(user.get("sub")))

    if date_from:
        query = query.filter(Appointment.appointment_date >= date_from)
    if date_to:
        query = query.filter(Appointment.appointment_date <= date_to)

    total = query.count()
    cancelled = query.filter(Appointment.status == "cancelled").count()
    no_show = query.filter(Appointment.status == "no_show").count()
    completed = query.filter(Appointment.status == "completed").count()

    return AppointmentStatsResponse(
        total_bookings=total,
        total_cancellations=cancelled,
        total_no_shows=no_show,
        total_completed=completed,
    )
