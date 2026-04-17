from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class PatientProfileCreate(BaseModel):
    user_id: UUID
    email: EmailStr
    phone: Optional[str] = None
    full_name: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[str] = None
    nic_passport: Optional[str] = None


class PatientProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    profile_image_url: Optional[str] = None
    nic_passport: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            return None
        if not normalized.replace("+", "").replace(" ", "").replace("-", "").isdigit():
            raise ValueError("Invalid phone number format")
        if len(normalized.replace("+", "").replace(" ", "").replace("-", "")) < 7:
            raise ValueError("Invalid phone number format")
        return normalized

    @field_validator("profile_image_url")
    @classmethod
    def validate_profile_image_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed_extensions = (".jpg", ".jpeg", ".png", ".webp")
        if not value.lower().endswith(allowed_extensions):
            raise ValueError("Unsupported profile image format")
        return value


class PatientProfileResponse(BaseModel):
    patient_id: UUID
    user_id: UUID
    email: EmailStr
    pending_email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    profile_image_url: Optional[str] = None
    full_name: str
    dob: Optional[date] = None
    gender: Optional[str] = None
    nic_passport: Optional[str] = None
    profile_status: str
    profile_completion: int = 0
    created_at: datetime

    class Config:
        from_attributes = True
