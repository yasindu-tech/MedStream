from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class PatientProfileCreate(BaseModel):
    user_id: UUID
    email: EmailStr
    phone: Optional[str] = None
    full_name: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[str] = None
    nic_passport: Optional[str] = None


class PatientProfileResponse(BaseModel):
    patient_id: UUID
    user_id: UUID
    email: EmailStr
    phone: Optional[str] = None
    full_name: str
    dob: Optional[date] = None
    gender: Optional[str] = None
    nic_passport: Optional[str] = None
    profile_status: str
    created_at: datetime

    class Config:
        from_attributes = True
