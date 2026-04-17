from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services import create_verified_user, deactivate_user, suspend_user
from app.services.appointment_client import (
    get_doctor_pending_future_appointments,
    get_patient_pending_future_appointments,
)


class ClinicAdminOnboardingRequest(BaseModel):
    email: EmailStr
    password: str
    phone: Optional[str] = None


class ClinicAdminOnboardingResponse(BaseModel):
    id: str
    email: EmailStr


class ClinicStaffOnboardingRequest(BaseModel):
    email: EmailStr
    password: str
    phone: Optional[str] = None


class ClinicStaffOnboardingResponse(BaseModel):
    id: str
    email: EmailStr


class SuspendUserRequest(BaseModel):
    reason: Optional[str] = None


router = APIRouter(tags=["internal"])


@router.post("/clinic-admin", response_model=ClinicAdminOnboardingResponse, status_code=status.HTTP_201_CREATED)
def create_clinic_admin_user(data: ClinicAdminOnboardingRequest, db: Session = Depends(get_db)):
    user = create_verified_user(
        email=data.email,
        password=data.password,
        phone=data.phone,
        role_name="clinic_admin",
        db=db,
    )
    return {"id": str(user["id"]), "email": user["email"]}


@router.post("/clinic-admin/{user_id}/deactivate", status_code=status.HTTP_200_OK)
def deactivate_clinic_admin_user(user_id: UUID, db: Session = Depends(get_db)):
    from app.services import deactivate_user

    deactivate_user(user_id, db)
    return {"success": True}


@router.post("/clinic-staff", response_model=ClinicStaffOnboardingResponse, status_code=status.HTTP_201_CREATED)
def create_clinic_staff_user(data: ClinicStaffOnboardingRequest, db: Session = Depends(get_db)):
    user = create_verified_user(
        email=data.email,
        password=data.password,
        phone=data.phone,
        role_name="clinic_staff",
        db=db,
    )
    return {"id": str(user["id"]), "email": user["email"]}


@router.post("/clinic-staff/{user_id}/deactivate", status_code=status.HTTP_200_OK)
def deactivate_clinic_staff_user(user_id: UUID, db: Session = Depends(get_db)):
    from app.services import deactivate_user

    deactivate_user(user_id, db)
    return {"success": True}


@router.post("/users/{user_id}/suspend", status_code=status.HTTP_200_OK)
def suspend_user_account(user_id: UUID, payload: SuspendUserRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if "doctor" in user.role_names:
        pending = get_doctor_pending_future_appointments(str(user_id))
        if pending > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Doctor has active or upcoming consultations and cannot be suspended.",
            )

    if "patient" in user.role_names:
        pending = get_patient_pending_future_appointments(str(user_id))
        if pending > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Patient has active or upcoming consultations and cannot be suspended.",
            )

    suspend_user(user_id, reason=payload.reason, db=db)
    return {"success": True}
