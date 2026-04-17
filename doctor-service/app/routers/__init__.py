"""Internal router — not exposed through the nginx gateway.

All routes under /internal/* are for service-to-service calls only.
No JWT auth is applied here; network-level isolation is the security boundary.
"""
from __future__ import annotations
from datetime import date
import hmac
import os
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Doctor
from app.schemas import (
    DoctorSearchResponse,
    DoctorProfileResponse,
    DoctorAvailabilityCreateRequest,
    DoctorAvailabilityListResponse,
    DoctorAvailabilityResponse,
    DoctorAvailabilityUpdateRequest,
    DoctorClinicAssignmentListResponse,
    DoctorCreateRequest,
    DoctorIdResponse,
    DoctorLeaveListResponse,
    DoctorLeaveRequest,
    DoctorLeaveResponse,
    DoctorUpdateRequest,
    DoctorVisibilityRequest,
    DoctorVerificationActionRequest,
    DoctorSuspendRequest,
    DoctorVerificationActionResponse,
    DoctorProfileHistoryListResponse,
    PendingDoctorItem,
    PendingDoctorListResponse,
    SlotValidationResponse,
    DoctorVerificationDetailsResponse,
)
from app.services.doctor_search import search_doctors
from app.services.doctor_profile import (
    create_doctor_profile,
    get_doctor_profile,
    list_assigned_clinics,
    list_doctor_profile_history,
    update_doctor_profile,
)
from app.services.doctor_schedule import (
    create_doctor_availability,
    delete_doctor_availability,
    list_doctor_availability,
    update_doctor_availability,
)
from app.services.doctor_leave import (
    create_doctor_leave,
    delete_doctor_leave,
    list_doctor_leaves,
)
from app.services.doctor_verification import (
    get_doctor_verification_documents,
    list_pending_doctors,
    reactivate_doctor_profile,
    review_doctor_verification,
    suspend_doctor_profile,
)
from app.services.slot_validator import validate_slot


def _require_internal_service_auth(
    x_internal_service_token: str | None = Header(default=None, alias="X-Internal-Service-Token"),
) -> None:
    expected_token = os.getenv("INTERNAL_SERVICE_TOKEN")
    if not expected_token or not x_internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized internal request",
        )

    if not hmac.compare_digest(x_internal_service_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized internal request",
        )


router = APIRouter(
    tags=["internal"],
    dependencies=[Depends(_require_internal_service_auth)],
)


# ---------------------------------------------------------------------------
# AS-01: Doctor search
# ---------------------------------------------------------------------------

@router.get("/doctors/search", response_model=DoctorSearchResponse)
def internal_doctor_search(
    specialty: Optional[str] = Query(None, description="Filter by specialization (partial match)"),
    date: Optional[date] = Query(None, description="Target date for slot availability (YYYY-MM-DD)"),
    consultation_type: Optional[str] = Query(None, description="'physical' or 'telemedicine'"),
    clinic_id: Optional[UUID] = Query(None, description="Restrict to a specific clinic"),
    db: Session = Depends(get_db),
) -> DoctorSearchResponse:
    """
    Internal endpoint consumed by appointment-service.
    Returns matching doctors with available time slots.

    - Returns 200 with [] when no doctors match — never 404.
    - Doctors with no available slots are included with has_slots=false.
    - Sorted by earliest available slot; no-slot doctors are last.
    """
    results = search_doctors(
        db,
        specialty=specialty,
        target_date=date,
        consultation_type=consultation_type,
        clinic_id=clinic_id,
    )
    return DoctorSearchResponse(
        results=results,
        total=len(results),
        empty_state=len(results) == 0,
    )


# ---------------------------------------------------------------------------
# AS-02: Doctor profile
# ---------------------------------------------------------------------------

@router.get("/doctors/{doctor_id}/profile", response_model=DoctorProfileResponse)
def internal_doctor_profile(
    doctor_id: UUID,
    date: Optional[date] = Query(None, description="Target date for slot availability (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> DoctorProfileResponse:
    """
    Internal endpoint consumed by appointment-service.
    Returns full doctor profile with clinic details and availability.

    Returns 404 if doctor is not found, inactive, or unverified.
    """
    profile = get_doctor_profile(db, doctor_id, target_date=date)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Doctor not found, inactive, or unverified",
        )
    return profile


# ---------------------------------------------------------------------------
# AS-01b: Create / update doctor profile
# ---------------------------------------------------------------------------

@router.post("/doctors", response_model=DoctorIdResponse)
def internal_create_doctor_profile(
    payload: DoctorCreateRequest,
    db: Session = Depends(get_db),
) -> DoctorIdResponse:
    doctor = create_doctor_profile(
        db=db,
        user_id=payload.user_id,
        full_name=payload.full_name,
        medical_registration_no=payload.medical_registration_no,
        specialization=payload.specialization,
        consultation_mode=payload.consultation_mode,
        bio=payload.bio,
        experience_years=payload.experience_years,
        qualifications=payload.qualifications,
        profile_image_url=payload.profile_image_url,
        consultation_fee=payload.consultation_fee,
    )
    return DoctorIdResponse(doctor_id=doctor.doctor_id, full_name=doctor.full_name)


@router.patch("/doctors/{doctor_id}", response_model=DoctorIdResponse)
def internal_update_doctor_profile(
    doctor_id: UUID,
    payload: DoctorUpdateRequest,
    db: Session = Depends(get_db),
) -> DoctorIdResponse:
    doctor = update_doctor_profile(
        db=db,
        doctor_id=doctor_id,
        full_name=payload.full_name,
        medical_registration_no=payload.medical_registration_no,
        specialization=payload.specialization,
        consultation_mode=payload.consultation_mode,
        bio=payload.bio,
        experience_years=payload.experience_years,
        qualifications=payload.qualifications,
        profile_image_url=payload.profile_image_url,
        consultation_fee=payload.consultation_fee,
    )
    return DoctorIdResponse(doctor_id=doctor.doctor_id, full_name=doctor.full_name)


@router.post("/doctors/{doctor_id}/visibility", response_model=DoctorVerificationActionResponse)
def internal_set_doctor_visibility(
    doctor_id: UUID,
    payload: DoctorVisibilityRequest,
    db: Session = Depends(get_db),
) -> DoctorVerificationActionResponse:
    doctor = db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found.")

    if doctor.status == "suspended":
        raise HTTPException(
            status_code=409,
            detail="Suspended doctor profiles cannot change visibility.",
        )

    if payload.visible:
        if doctor.verification_status != "verified":
            raise HTTPException(
                status_code=409,
                detail="Doctor must be verified before becoming visible for booking.",
            )
        doctor.status = "active"
    else:
        doctor.status = "hidden"

    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return DoctorVerificationActionResponse(
        doctor_id=doctor.doctor_id,
        verification_status=doctor.verification_status,
        verification_rejection_reason=doctor.verification_rejection_reason,
    )


@router.post("/doctors/{doctor_id}/reactivate", response_model=DoctorVerificationActionResponse)
def internal_reactivate_doctor_profile(
    doctor_id: UUID,
    db: Session = Depends(get_db),
) -> DoctorVerificationActionResponse:
    doctor = reactivate_doctor_profile(db=db, doctor_id=doctor_id)
    return DoctorVerificationActionResponse(
        doctor_id=doctor.doctor_id,
        verification_status=doctor.verification_status,
        verification_rejection_reason=doctor.verification_rejection_reason,
    )


# ---------------------------------------------------------------------------
# AS-05: Clinic assignment visibility
# ---------------------------------------------------------------------------

@router.get("/doctors/{doctor_id}/clinics", response_model=DoctorClinicAssignmentListResponse)
def internal_get_doctor_clinics(
    doctor_id: UUID,
    db: Session = Depends(get_db),
) -> DoctorClinicAssignmentListResponse:
    clinics = list_assigned_clinics(db, doctor_id)
    return DoctorClinicAssignmentListResponse(results=clinics, total=len(clinics))


# ---------------------------------------------------------------------------
# AS-09: Availability management
# ---------------------------------------------------------------------------

@router.get("/doctors/{doctor_id}/availability", response_model=DoctorAvailabilityListResponse)
def internal_list_doctor_availability(
    doctor_id: UUID,
    db: Session = Depends(get_db),
) -> DoctorAvailabilityListResponse:
    availability = list_doctor_availability(db, doctor_id)
    return DoctorAvailabilityListResponse(results=availability, total=len(availability))


@router.get("/doctors/{doctor_id}/history", response_model=DoctorProfileHistoryListResponse)
def internal_get_doctor_profile_history(
    doctor_id: UUID,
    db: Session = Depends(get_db),
) -> DoctorProfileHistoryListResponse:
    history_items = list_doctor_profile_history(db, doctor_id)
    return DoctorProfileHistoryListResponse(results=history_items, total=len(history_items))


@router.post("/doctors/{doctor_id}/availability", response_model=DoctorAvailabilityResponse)
def internal_create_doctor_availability(
    doctor_id: UUID,
    payload: DoctorAvailabilityCreateRequest,
    db: Session = Depends(get_db),
) -> DoctorAvailabilityResponse:
    availability = create_doctor_availability(db=db, doctor_id=doctor_id, payload=payload)
    return DoctorAvailabilityResponse(
        availability_id=availability.availability_id,
        clinic_id=availability.clinic_id,
        day_of_week=availability.day_of_week,
        date=availability.date.isoformat() if availability.date else None,
        start_time=availability.start_time,
        end_time=availability.end_time,
        slot_duration=availability.slot_duration,
        consultation_type=availability.consultation_type,
        status=availability.status,
    )


@router.patch("/doctors/{doctor_id}/availability/{availability_id}", response_model=DoctorAvailabilityResponse)
def internal_update_doctor_availability(
    doctor_id: UUID,
    availability_id: UUID,
    payload: DoctorAvailabilityUpdateRequest,
    db: Session = Depends(get_db),
) -> DoctorAvailabilityResponse:
    availability = update_doctor_availability(
        db=db,
        doctor_id=doctor_id,
        availability_id=availability_id,
        payload=payload,
    )
    return DoctorAvailabilityResponse(
        availability_id=availability.availability_id,
        clinic_id=availability.clinic_id,
        day_of_week=availability.day_of_week,
        date=availability.date.isoformat() if availability.date else None,
        start_time=availability.start_time,
        end_time=availability.end_time,
        slot_duration=availability.slot_duration,
        consultation_type=availability.consultation_type,
        status=availability.status,
    )


@router.delete("/doctors/{doctor_id}/availability/{availability_id}", response_model=DoctorAvailabilityResponse)
def internal_delete_doctor_availability(
    doctor_id: UUID,
    availability_id: UUID,
    db: Session = Depends(get_db),
) -> DoctorAvailabilityResponse:
    availability = delete_doctor_availability(db=db, doctor_id=doctor_id, availability_id=availability_id)
    return DoctorAvailabilityResponse(
        availability_id=availability.availability_id,
        clinic_id=availability.clinic_id,
        day_of_week=availability.day_of_week,
        date=availability.date.isoformat() if availability.date else None,
        start_time=availability.start_time,
        end_time=availability.end_time,
        slot_duration=availability.slot_duration,
        consultation_type=availability.consultation_type,
        status=availability.status,
    )


# ---------------------------------------------------------------------------
# AS-11: Leave / unavailable date management
# ---------------------------------------------------------------------------

@router.post("/doctors/{doctor_id}/leave", response_model=DoctorLeaveResponse)
def internal_create_doctor_leave(
    doctor_id: UUID,
    payload: DoctorLeaveRequest,
    db: Session = Depends(get_db),
) -> DoctorLeaveResponse:
    leave = create_doctor_leave(db=db, doctor_id=doctor_id, payload=payload)
    return DoctorLeaveResponse(
        leave_id=leave.leave_id,
        clinic_id=leave.clinic_id,
        start_datetime=leave.start_datetime.isoformat(),
        end_datetime=leave.end_datetime.isoformat(),
        reason=leave.reason,
        status=leave.status,
    )


@router.get("/doctors/{doctor_id}/leave", response_model=DoctorLeaveListResponse)
def internal_list_doctor_leaves(
    doctor_id: UUID,
    db: Session = Depends(get_db),
) -> DoctorLeaveListResponse:
    leaves = list_doctor_leaves(db, doctor_id)
    return DoctorLeaveListResponse(results=leaves, total=len(leaves))


@router.delete("/doctors/{doctor_id}/leave/{leave_id}", response_model=DoctorLeaveResponse)
def internal_delete_doctor_leave(
    doctor_id: UUID,
    leave_id: UUID,
    db: Session = Depends(get_db),
) -> DoctorLeaveResponse:
    leave = delete_doctor_leave(db=db, doctor_id=doctor_id, leave_id=leave_id)
    return DoctorLeaveResponse(
        leave_id=leave.leave_id,
        clinic_id=leave.clinic_id,
        start_datetime=leave.start_datetime.isoformat(),
        end_datetime=leave.end_datetime.isoformat(),
        reason=leave.reason,
        status=leave.status,
    )


# ---------------------------------------------------------------------------
# AS-04: Pending verification
# ---------------------------------------------------------------------------

@router.get("/doctors/pending", response_model=PendingDoctorListResponse)
def internal_list_pending_doctors(
    db: Session = Depends(get_db),
) -> PendingDoctorListResponse:
    pending = list_pending_doctors(db)
    items = [
        PendingDoctorItem(
            doctor_id=doctor.doctor_id,
            full_name=doctor.full_name,
            specialization=doctor.specialization,
            consultation_mode=doctor.consultation_mode,
            medical_registration_no=doctor.medical_registration_no,
            verification_status=doctor.verification_status,
            status=doctor.status,
            has_documents=bool(doctor.verification_documents),
            missing_documents=not bool(doctor.verification_documents),
        )
        for doctor in pending
    ]
    return PendingDoctorListResponse(results=items, total=len(items))


@router.get("/doctors/{doctor_id}/verification-documents", response_model=DoctorVerificationDetailsResponse)
def internal_doctor_verification_documents(
    doctor_id: UUID,
    db: Session = Depends(get_db),
) -> DoctorVerificationDetailsResponse:
    doctor = get_doctor_verification_documents(db, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found.")

    documents = doctor.verification_documents or []
    return DoctorVerificationDetailsResponse(
        doctor_id=doctor.doctor_id,
        full_name=doctor.full_name,
        medical_registration_no=doctor.medical_registration_no,
        verification_status=doctor.verification_status,
        status=doctor.status,
        verification_documents=[
            {
                "name": doc.get("name", "document"),
                "url": doc.get("url", ""),
                "uploaded_at": doc.get("uploaded_at"),
                "status": doc.get("status"),
            }
            for doc in documents
        ],
        missing_documents=not bool(documents),
        verification_rejection_reason=doctor.verification_rejection_reason,
    )


@router.post("/doctors/{doctor_id}/verification", response_model=DoctorVerificationActionResponse)
def internal_review_doctor_verification(
    doctor_id: UUID,
    payload: DoctorVerificationActionRequest,
    db: Session = Depends(get_db),
) -> DoctorVerificationActionResponse:
    doctor = review_doctor_verification(
        db=db,
        doctor_id=doctor_id,
        action=payload.action,
        reason=payload.reason,
    )
    return DoctorVerificationActionResponse(
        doctor_id=doctor.doctor_id,
        verification_status=doctor.verification_status,
        verification_rejection_reason=doctor.verification_rejection_reason,
    )


@router.post("/doctors/{doctor_id}/suspend", response_model=DoctorVerificationActionResponse)
def internal_suspend_doctor(
    doctor_id: UUID,
    payload: DoctorSuspendRequest,
    db: Session = Depends(get_db),
) -> DoctorVerificationActionResponse:
    doctor = suspend_doctor_profile(db=db, doctor_id=doctor_id, reason=payload.reason)
    return DoctorVerificationActionResponse(
        doctor_id=doctor.doctor_id,
        verification_status=doctor.verification_status,
        verification_rejection_reason=doctor.verification_rejection_reason,
    )


# ---------------------------------------------------------------------------
# AS-03: Slot validation
# ---------------------------------------------------------------------------

@router.get("/doctors/{doctor_id}/validate-slot", response_model=SlotValidationResponse)
def internal_validate_slot(
    doctor_id: UUID,
    clinic_id: UUID = Query(..., description="Clinic UUID"),
    date: date = Query(..., description="Target date (YYYY-MM-DD)"),
    start_time: str = Query(..., description="Slot start time (HH:MM)"),
    consultation_type: str = Query(..., description="'physical' or 'telemedicine'"),
    db: Session = Depends(get_db),
) -> SlotValidationResponse:
    """
    Lightweight slot validation for the booking flow.
    Confirms doctor/clinic/day/time/consultation_type are all valid and bookable.
    """
    result = validate_slot(
        db,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
        target_date=date,
        start_time=start_time,
        consultation_type=consultation_type,
    )
    return SlotValidationResponse(**result)


# ---------------------------------------------------------------------------
# AS-04: Resolve user_id to doctor_id
# ---------------------------------------------------------------------------

@router.get("/doctors/by-user/{user_id}", response_model=DoctorIdResponse)
def internal_doctor_by_user(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> DoctorIdResponse:
    """
    Internal endpoint to resolve an auth user_id to an admin DB doctor_id.
    """
    doctor = db.query(Doctor).filter(Doctor.user_id == user_id).first()
    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor profile not found for this user",
        )

    return DoctorIdResponse(
        doctor_id=doctor.doctor_id,
        full_name=doctor.full_name,
    )

