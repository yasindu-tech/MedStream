from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.models import Doctor
from app.schemas import (
    DoctorAvailabilityCreateRequest,
    DoctorAvailabilityListResponse,
    DoctorAvailabilityResponse,
    DoctorAvailabilityUpdateRequest,
    DoctorConsultationFeeUpdateRequest,
    DoctorProfileResponse,
    DoctorUpdateRequest,
)
from app.services.doctor_profile import get_doctor_profile, update_doctor_profile
from app.services.doctor_schedule import (
    create_doctor_availability,
    delete_doctor_availability,
    list_doctor_availability,
    update_doctor_availability,
)

router = APIRouter(tags=["Doctor Public"])


def _resolve_current_doctor(user: dict, db: Session) -> Doctor:
    user_sub = user.get("sub")
    try:
        user_id = UUID(str(user_sub))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token")

    doctor = db.query(Doctor).filter(Doctor.user_id == user_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found for this user")
    return doctor


def _serialize_availability(availability) -> DoctorAvailabilityResponse:
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


def _get_current_doctor_profile(
    db: Session,
    doctor: Doctor,
    target_date: date | None = None,
) -> DoctorProfileResponse:
    profile = get_doctor_profile(db, doctor.doctor_id, target_date=target_date)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found, inactive, or unverified",
        )
    return profile


@router.get("/me", response_model=DoctorProfileResponse)
def get_my_doctor_profile(
    target_date: date | None = Query(
        default=None,
        alias="date",
        description="Optional date (YYYY-MM-DD) to compute available slots",
    ),
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> DoctorProfileResponse:
    doctor = _resolve_current_doctor(user, db)
    return _get_current_doctor_profile(db, doctor, target_date=target_date)


@router.patch("/me", response_model=DoctorProfileResponse)
def update_my_doctor_profile(
    payload: DoctorUpdateRequest,
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> DoctorProfileResponse:
    doctor = _resolve_current_doctor(user, db)
    updated_doctor = update_doctor_profile(
        db=db,
        doctor_id=doctor.doctor_id,
        full_name=payload.full_name,
        medical_registration_no=payload.medical_registration_no,
        specialization=payload.specialization,
        specializations=payload.specializations,
        primary_specialization=payload.primary_specialization,
        consultation_mode=payload.consultation_mode,
        bio=payload.bio,
        experience_years=payload.experience_years,
        qualifications=payload.qualifications,
        profile_image_url=payload.profile_image_url,
        consultation_fee=payload.consultation_fee,
    )
    return _get_current_doctor_profile(db, updated_doctor)


@router.patch("/me/consultation-fee", response_model=DoctorProfileResponse)
def update_my_consultation_fee(
    payload: DoctorConsultationFeeUpdateRequest,
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> DoctorProfileResponse:
    doctor = _resolve_current_doctor(user, db)
    updated_doctor = update_doctor_profile(
        db=db,
        doctor_id=doctor.doctor_id,
        consultation_fee=payload.consultation_fee,
    )
    return _get_current_doctor_profile(db, updated_doctor)


@router.get("/me/availability", response_model=DoctorAvailabilityListResponse)
def get_my_doctor_availability(
    clinic_id: UUID | None = Query(default=None, description="Optional clinic UUID filter"),
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> DoctorAvailabilityListResponse:
    doctor = _resolve_current_doctor(user, db)
    results = list_doctor_availability(db, doctor.doctor_id)
    if clinic_id is not None:
        results = [item for item in results if item.clinic_id == clinic_id]
    return DoctorAvailabilityListResponse(results=results, total=len(results))


@router.post("/me/availability", response_model=DoctorAvailabilityResponse)
def create_my_doctor_availability(
    payload: DoctorAvailabilityCreateRequest,
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> DoctorAvailabilityResponse:
    doctor = _resolve_current_doctor(user, db)
    availability = create_doctor_availability(
        db=db,
        doctor_id=doctor.doctor_id,
        payload=payload,
    )
    return _serialize_availability(availability)


@router.patch("/me/availability/{availability_id}", response_model=DoctorAvailabilityResponse)
def update_my_doctor_availability(
    availability_id: UUID,
    payload: DoctorAvailabilityUpdateRequest,
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> DoctorAvailabilityResponse:
    doctor = _resolve_current_doctor(user, db)
    availability = update_doctor_availability(
        db=db,
        doctor_id=doctor.doctor_id,
        availability_id=availability_id,
        payload=payload,
    )
    return _serialize_availability(availability)


@router.delete("/me/availability/{availability_id}", response_model=DoctorAvailabilityResponse)
def delete_my_doctor_availability(
    availability_id: UUID,
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> DoctorAvailabilityResponse:
    doctor = _resolve_current_doctor(user, db)
    availability = delete_doctor_availability(
        db=db,
        doctor_id=doctor.doctor_id,
        availability_id=availability_id,
    )
    return _serialize_availability(availability)
