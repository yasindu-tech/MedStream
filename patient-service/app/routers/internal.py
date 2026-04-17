from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Patient
from app.schemas import PatientProfileCreate, PatientProfileResponse

router = APIRouter(tags=["internal"])


@router.post("/patients", response_model=PatientProfileResponse, status_code=201)
def create_patient_profile(request: PatientProfileCreate, db: Session = Depends(get_db)) -> PatientProfileResponse:
    existing_by_user = db.query(Patient).filter(Patient.user_id == request.user_id).first()
    if existing_by_user:
        return existing_by_user

    existing_by_email = db.query(Patient).filter(Patient.email == request.email).first()
    if existing_by_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A patient profile already exists for this email.",
        )

    full_name = request.full_name or Patient.build_full_name(request.email)
    patient = Patient(
        user_id=request.user_id,
        email=request.email,
        phone=request.phone,
        full_name=full_name,
        dob=request.dob,
        gender=request.gender,
        nic_passport=request.nic_passport,
        profile_status="active",
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient
