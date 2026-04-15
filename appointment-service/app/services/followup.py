"""Follow-up appointment logic."""
from __future__ import annotations
from datetime import date, time, datetime
from typing import Optional, List
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Appointment, Patient, FollowUpSuggestion
from app.schemas import FollowUpSuggestRequest, FollowUpSuggestionResponse, BookAppointmentRequest
from app.services.booking import book_appointment, _validate_slot_with_doctor_service


def _get_doctor_info_by_user(user_id: str) -> dict:
    """Call doctor-service to resolve a user_id to a doctor_id."""
    url = f"{settings.DOCTOR_SERVICE_URL}/internal/doctors/by-user/{user_id}"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have a linked doctor profile, cannot suggest follow-up.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Doctor service resolution error: {exc.response.status_code}",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Doctor service is currently unavailable. Please try again later.",
        )


def suggest_followup(
    db: Session,
    *,
    doctor_user_id: str,
    request: FollowUpSuggestRequest,
) -> FollowUpSuggestionResponse:
    """
    Called by a doctor to suggest a follow-up appointment.
    """
    # 1. Resolve user_id to doctor_id
    doctor_info = _get_doctor_info_by_user(doctor_user_id)
    doctor_id = UUID(doctor_info["doctor_id"])
    doctor_name = doctor_info["full_name"]

    # 2. Verify original appointment exists, belongs to this doctor, and is valid
    original_appt = (
        db.query(Appointment)
        .filter(Appointment.appointment_id == request.original_appointment_id)
        .first()
    )
    if not original_appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original appointment not found."
        )
    if original_appt.doctor_id != doctor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only suggest follow-ups for your own appointments."
        )

    # 3. Validate suggested slot
    val_req = BookAppointmentRequest(
        doctor_id=doctor_id,
        clinic_id=original_appt.clinic_id,
        date=request.suggested_date,
        start_time=request.suggested_start_time,
        consultation_type=request.consultation_type,
    )
    slot_info = _validate_slot_with_doctor_service(val_req)
    if not slot_info.get("valid"):
        reason = slot_info.get("reason", "Slot is not valid")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=reason)

    # 4. Create suggestion
    start_time_obj = datetime.strptime(request.suggested_start_time, "%H:%M").time()
    end_time_obj = datetime.strptime(slot_info["end_time"], "%H:%M").time()

    suggestion = FollowUpSuggestion(
        original_appointment_id=original_appt.appointment_id,
        doctor_id=doctor_id,
        patient_id=original_appt.patient_id,
        clinic_id=original_appt.clinic_id,
        suggested_date=request.suggested_date,
        suggested_start_time=start_time_obj,
        suggested_end_time=end_time_obj,
        consultation_type=request.consultation_type,
        notes=request.notes,
        status="pending",
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    
    # 5. TODO: Send notification to the patient
    # Notification logic goes here (e.g., call notification-service)

    return FollowUpSuggestionResponse(
        suggestion_id=suggestion.suggestion_id,
        original_appointment_id=suggestion.original_appointment_id,
        doctor_id=suggestion.doctor_id,
        doctor_name=doctor_name,
        patient_id=suggestion.patient_id,
        clinic_id=suggestion.clinic_id,
        suggested_date=suggestion.suggested_date,
        suggested_start_time=suggestion.suggested_start_time.strftime("%H:%M"),
        suggested_end_time=suggestion.suggested_end_time.strftime("%H:%M"),
        consultation_type=suggestion.consultation_type,
        notes=suggestion.notes,
        status=suggestion.status,
        message="Follow-up suggestion created successfully.",
    )


def confirm_followup(
    db: Session,
    *,
    patient_user_id: str,
    suggestion_id: UUID,
) -> dict:
    """
    Called by a patient to confirm a follow-up appointment suggestion.
    """
    # 1. Fetch patient
    patient = db.query(Patient).filter(Patient.user_id == UUID(patient_user_id)).first()
    if not patient:
         raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found."
         )

    # 2. Fetch suggestion and verify it belongs to patient and is pending
    suggestion = db.query(FollowUpSuggestion).filter(FollowUpSuggestion.suggestion_id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found."
        )
    if suggestion.patient_id != patient.patient_id:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only confirm your own follow-up suggestions."
         )
    if suggestion.status != "pending":
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot confirm suggestion because its status is '{suggestion.status}'."
         )

    # 3. Create BookAppointmentRequest out of suggestion
    book_req = BookAppointmentRequest(
        doctor_id=suggestion.doctor_id,
        clinic_id=suggestion.clinic_id,
        date=suggestion.suggested_date,
        start_time=suggestion.suggested_start_time.strftime("%H:%M"),
        consultation_type=suggestion.consultation_type,
    )

    # 4. Use standard book_appointment logic
    # This will cleanly re-verify via doctor-service and detect any conflicts
    result = book_appointment(db, patient_id=patient_user_id, request=book_req)
    
    # 5. Link the original appointment as parent
    appt = db.query(Appointment).filter(Appointment.appointment_id == result.appointment_id).first()
    if appt:
        appt.parent_appointment_id = suggestion.original_appointment_id
    
    # 6. Update suggestion status
    suggestion.status = "confirmed"
    db.commit()

    return result


def get_pending_followups(
    db: Session,
    *,
    patient_user_id: str,
) -> List[FollowUpSuggestionResponse]:
    """
    Fetch all 'pending' follow-up suggestions for the logged-in patient.
    """
    patient = db.query(Patient).filter(Patient.user_id == UUID(patient_user_id)).first()
    if not patient:
        return []

    suggestions = (
        db.query(FollowUpSuggestion)
        .filter(FollowUpSuggestion.patient_id == patient.patient_id, FollowUpSuggestion.status == "pending")
        .all()
    )

    responses = []
    
    # Simple cache to avoid redundant calls for same doctor
    doctor_names = {}

    for s in suggestions:
        doctor_id_str = str(s.doctor_id)
        if doctor_id_str not in doctor_names:
            url = f"{settings.DOCTOR_SERVICE_URL}/internal/doctors/{doctor_id_str}/profile"
            try:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        doctor_names[doctor_id_str] = resp.json().get("full_name", "Unknown Doctor")
                    else:
                        doctor_names[doctor_id_str] = f"Doctor (ID: {doctor_id_str})"
            except Exception:
                doctor_names[doctor_id_str] = f"Doctor (ID: {doctor_id_str})"

        responses.append(FollowUpSuggestionResponse(
            suggestion_id=s.suggestion_id,
            original_appointment_id=s.original_appointment_id,
            doctor_id=s.doctor_id,
            doctor_name=doctor_names[doctor_id_str],
            patient_id=s.patient_id,
            clinic_id=s.clinic_id,
            suggested_date=s.suggested_date,
            suggested_start_time=s.suggested_start_time.strftime("%H:%M"),
            suggested_end_time=s.suggested_end_time.strftime("%H:%M"),
            consultation_type=s.consultation_type,
            notes=s.notes,
            status=s.status,
            message="",
        ))
        
    return responses
