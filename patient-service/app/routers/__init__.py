from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Patient
from app.schemas import PatientProfileResponse, PatientProfileUpdate

router = APIRouter(tags=["Patient Profiles"])


@router.get("/me", response_model=PatientProfileResponse)
def get_my_patient_profile(user_id: UUID = Query(..., description="Current patient user ID"), db: Session = Depends(get_db)) -> PatientProfileResponse:
    patient = db.query(Patient).filter(Patient.user_id == user_id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")
    return patient


@router.get("/by-user/{user_id}", response_model=PatientProfileResponse)
def get_patient_profile_by_user_id(user_id: UUID, db: Session = Depends(get_db)) -> PatientProfileResponse:
    patient = db.query(Patient).filter(Patient.user_id == user_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient


@router.get("/patients/{patient_id}", response_model=PatientProfileResponse)
def get_patient_profile(patient_id: UUID, db: Session = Depends(get_db)) -> PatientProfileResponse:
    patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient


@router.patch("/patients/{patient_id}", response_model=PatientProfileResponse)
def update_patient_profile(patient_id: UUID, request: PatientProfileUpdate, db: Session = Depends(get_db)) -> PatientProfileResponse:
    patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")

    if request.nic_passport is not None and request.nic_passport != patient.nic_passport:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="NIC/passport changes require admin approval.",
        )

    if request.email is not None and request.email != patient.email:
        existing_email = db.query(Patient).filter(Patient.email == request.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email address is already in use.",
            )
        patient.pending_email = request.email
        patient.profile_status = "pending_email_verification"

    if request.address is not None:
        patient.address = request.address

    if request.phone is not None:
        patient.phone = request.phone

    if request.emergency_contact is not None:
        patient.emergency_contact = request.emergency_contact

    if request.profile_image_url is not None:
        patient.profile_image_url = request.profile_image_url

    db.commit()
    db.refresh(patient)
    return patient
