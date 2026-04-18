import logging
import secrets
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.models import Doctor
from app.services.auth_client import register_doctor_user, deactivate_doctor_user
from app.services.notification_client import queue_doctor_onboarding_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/doctors", tags=["Admin Doctors"])


class DoctorCreateRequest(BaseModel):
    full_name: str
    email: EmailStr
    medical_registration_no: str | None = None
    specialization: str | None = None
    consultation_mode: str | None = None
    consultation_fee: float | None = None
    status: str = "active"


class DoctorUpdateRequest(BaseModel):
    full_name: str | None = None
    medical_registration_no: str | None = None
    specialization: str | None = None
    consultation_mode: str | None = None
    consultation_fee: float | None = None
    status: str | None = None


class DoctorResponse(BaseModel):
    doctor_id: UUID
    full_name: str
    medical_registration_no: str | None = None
    specialization: str | None = None
    consultation_mode: str | None = None
    consultation_fee: float | None = None
    status: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[DoctorResponse])
def get_all_doctors(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("admin", "clinic_admin")),
):
    doctors = db.query(Doctor).all()
    return doctors


@router.post("", response_model=DoctorResponse, status_code=status.HTTP_201_CREATED)
def create_doctor(
    payload: DoctorCreateRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("admin")),
):
    temp_password = secrets.token_urlsafe(12)
    try:
        auth_user = register_doctor_user(
            email=payload.email,
            password=temp_password,
            full_name=payload.full_name,
        )
    except HTTPException:
        raise

    new_doc = Doctor(
        user_id=auth_user.get("id"),
        full_name=payload.full_name,
        medical_registration_no=payload.medical_registration_no,
        specialization=payload.specialization,
        consultation_mode=payload.consultation_mode,
        consultation_fee=payload.consultation_fee,
        status=payload.status,
    )
    db.add(new_doc)
    db.flush()
    db.commit()
    db.refresh(new_doc)

    try:
        queue_doctor_onboarding_email(
            user_id=auth_user.get("id"),
            email=payload.email,
            full_name=payload.full_name,
            temporary_password=temp_password,
        )
    except Exception as exc:
        logger.warning(
            "Doctor created but onboarding email could not be queued: %s",
            exc,
        )

    return new_doc


@router.patch("/{doctor_id}", response_model=DoctorResponse)
def update_doctor(
    doctor_id: UUID,
    payload: DoctorUpdateRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("admin")),
):
    doctor = db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(doctor, key, value)

    db.commit()
    db.refresh(doctor)
    return doctor


@router.delete("/{doctor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doctor(
    doctor_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("admin")),
):
    doctor = db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    db.delete(doctor)
    db.commit()

    if doctor.user_id:
        try:
            deactivate_doctor_user(str(doctor.user_id))
        except Exception as exc:
            logger.warning("Failed to deactivate auth user for doctor %s: %s", doctor.doctor_id, exc)

    return None
