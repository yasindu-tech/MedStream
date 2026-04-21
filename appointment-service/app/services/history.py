"""Appointment history logic supporting filtering and multi-role array mapping securely."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import Appointment, Patient, TelemedicineSession
from app.schemas import AppointmentListItemResponse, AppointmentListPaginatedResponse
from app.services.clinic_scope import resolve_staff_clinic_id
from app.services.followup import _get_doctor_info_by_user
from app.services.policy import resolve_policy_for_appointment

def fetch_appointment_history(
    db: Session,
    user: dict,
    page: int = 1,
    size: int = 20,
    filter_date: Optional[date] = None,
    filter_status: Optional[str] = None,
    filter_type: Optional[str] = None,
) -> AppointmentListPaginatedResponse:
    """
    Returns unified appointment history list querying specifically against whoever requested it. 
    Doctor constraints limit it safely to their specific resolved doctor_id.
    Patient constraints bind seamlessly to the Patient Profile map natively.
    """
    query = db.query(Appointment, Patient).join(Patient, Appointment.patient_id == Patient.patient_id)
    
    role = user.get("role")
    user_id = user.get("sub")
    
    # 1. Bind structural ownership based upon incoming role 
    if role == "patient":
        patient = db.query(Patient).filter(Patient.user_id == UUID(user_id)).first()
        if not patient:
            # New patient has absolutely no history yet.
            return AppointmentListPaginatedResponse(items=[], total=0, page=page, size=size, has_more=False)
            
        query = query.filter(Appointment.patient_id == patient.patient_id)
        
    elif role == "doctor":
        # Resolve user_id -> doctor_id ensuring doctors never pull another clinic's pipeline
        doctor_info = _get_doctor_info_by_user(user_id)
        doctor_id = UUID(doctor_info["doctor_id"])
        query = query.filter(Appointment.doctor_id == doctor_id)
        
    elif role == "admin":
        pass
    elif role == "staff":
        clinic_id = resolve_staff_clinic_id(user_id)
        query = query.filter(Appointment.clinic_id == clinic_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unrecognized role for history access."
        )

    # 2. Append Optional Filters
    if filter_date:
        query = query.filter(Appointment.appointment_date == filter_date)
    if filter_status:
        query = query.filter(Appointment.status == filter_status)
    if filter_type:
        query = query.filter(Appointment.appointment_type == filter_type)

    # 3. Setup Order and Pagination 
    query = query.order_by(desc(Appointment.appointment_date), desc(Appointment.start_time))
    
    total = query.count()
    offset = (page - 1) * size
    results = query.offset(offset).limit(size).all()
    
    # 4. Construct Models mapping native caches seamlessly avoiding orphaned dependencies naturally!
    items = []
    for appt, pat in results:
        policy = resolve_policy_for_appointment(db, appt.policy_id)
        appointment_dt = datetime.combine(
            appt.appointment_date,
            appt.start_time,
            tzinfo=timezone.utc,
        )
        now_dt = datetime.now(timezone.utc)
        consultation_type = appt.appointment_type
        telemedicine_session = None
        if (consultation_type or "").lower() == "telemedicine":
            telemedicine_session = (
                db.query(TelemedicineSession)
                .filter(TelemedicineSession.appointment_id == appt.appointment_id)
                .first()
            )

        can_cancel = False
        can_reschedule = False
        if role == "patient":
            cancellable_statuses = {"confirmed", "pending_doctor", "pending_payment"}
            reschedulable_statuses = {"confirmed", "pending_doctor", "pending_payment"}
            can_cancel = (
                appt.status in cancellable_statuses
                and (appointment_dt - now_dt).total_seconds() >= policy.cancellation_window_hours * 3600
            )
            can_reschedule = (
                appt.status in reschedulable_statuses
                and appt.reschedule_count < policy.max_reschedules
                and (appointment_dt - now_dt).total_seconds() >= policy.reschedule_window_hours * 3600
            )

        items.append(
            AppointmentListItemResponse(
                appointment_id=appt.appointment_id,
                doctor_id=appt.doctor_id or UUID(int=0),
                doctor_name=appt.doctor_name or "Unknown Doctor (Historical)",
                clinic_id=appt.clinic_id or UUID(int=0),
                clinic_name=appt.clinic_name or "Unknown Clinic",
                patient_id=appt.patient_id,
                patient_name=pat.full_name,
                date=appt.appointment_date,
                start_time=appt.start_time.strftime("%H:%M"),
                end_time=appt.end_time.strftime("%H:%M"),
                status=appt.status,
                payment_status=appt.payment_status,
                consultation_type=consultation_type,
                can_cancel=can_cancel,
                can_reschedule=can_reschedule,
                reschedule_count=appt.reschedule_count or 0,
                max_reschedules=policy.max_reschedules,
                telemedicine_session_id=telemedicine_session.session_id if telemedicine_session else None,
                telemedicine_session_status=telemedicine_session.status if telemedicine_session else None,
                telemedicine_meeting_link=telemedicine_session.meeting_link if telemedicine_session else None,
                telemedicine_join_link_endpoint=(
                    "/telemedicine/sessions/join-link"
                    if telemedicine_session and (consultation_type or "").lower() == "telemedicine"
                    else None
                ),
            )
        )
        
    has_more = (offset + len(items)) < total
    
    return AppointmentListPaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        has_more=has_more
    )
