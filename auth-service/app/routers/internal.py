from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import create_verified_user


class ClinicAdminOnboardingRequest(BaseModel):
    email: EmailStr
    password: str
    phone: Optional[str] = None


class ClinicAdminOnboardingResponse(BaseModel):
    id: str
    email: EmailStr


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
