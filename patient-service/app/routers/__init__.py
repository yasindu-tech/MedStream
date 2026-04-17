from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Patient
from app.schemas import PatientProfileResponse

router = APIRouter(tags=["Patient Profiles"])


@router.get("/patients/by-user/{user_id}", response_model=PatientProfileResponse)
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
