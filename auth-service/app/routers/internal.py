from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services import create_verified_user, deactivate_user


class ClinicAdminOnboardingRequest(BaseModel):
    full_name: Optional[str] = None
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


class DoctorOnboardingRequest(BaseModel):
    full_name: Optional[str] = None
    email: EmailStr
    password: str
    phone: Optional[str] = None


class DoctorOnboardingResponse(BaseModel):
    id: str
    email: EmailStr



class InternalUserContactResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    phone: Optional[str] = None


router = APIRouter(tags=["internal"])


@router.post("/clinic-admin", response_model=ClinicAdminOnboardingResponse, status_code=status.HTTP_201_CREATED)
def create_clinic_admin_user(data: ClinicAdminOnboardingRequest, db: Session = Depends(get_db)):
    user = create_verified_user(
        full_name=data.full_name,
        email=data.email,
        password=data.password,
        phone=data.phone,
        role_name="clinic_admin",
        db=db,
    )
    return {"id": str(user["id"]), "email": user["email"]}


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
    deactivate_user(user_id=user_id, db=db)
    return {"success": True}


@router.post("/doctor", response_model=DoctorOnboardingResponse, status_code=status.HTTP_201_CREATED)
def create_doctor_user(data: DoctorOnboardingRequest, db: Session = Depends(get_db)):
    user = create_verified_user(
        full_name=data.full_name,
        email=data.email,
        password=data.password,
        phone=data.phone,
        role_name="doctor",
        db=db,
    )
    return {"id": str(user["id"]), "email": user["email"]}


@router.post("/doctor/{user_id}/deactivate", status_code=status.HTTP_200_OK)
def deactivate_internal_doctor_user(user_id: UUID, db: Session = Depends(get_db)):
    deactivate_user(user_id=user_id, db=db)
    return {"success": True}



@router.get("/users/{user_id}", response_model=InternalUserContactResponse)
def get_user_contact(user_id: UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "user_id": user.id,
        "email": user.email,
        "phone": user.phone,
    }
