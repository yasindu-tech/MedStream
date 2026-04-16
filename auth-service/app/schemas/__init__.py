from __future__ import annotations

from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

class RoleEnum(str, Enum):
    admin = "admin"
    doctor = "doctor"
    patient = "patient"
    staff = "staff"
    clinic_admin = "clinic_admin"
    clinic_staff = "clinic_staff"
    system_admin = "system_admin"

class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"

class OtpPurpose(str, Enum):
    REGISTER = "REGISTER"
    RESET_PASSWORD = "RESET_PASSWORD"

# --- Request Schemas ---
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    phone: Optional[str] = None
    role: RoleEnum = RoleEnum.patient

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str

class OTPRequest(BaseModel):
    email: EmailStr
    purpose: OtpPurpose

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp_code: str
    purpose: OtpPurpose
    new_password: Optional[str] = None

# --- Response Schemas ---
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class OTPResponse(BaseModel):
    otp_code: str

class UserResponse(BaseModel):
    id: UUID
    email: str
    phone: Optional[str] = None
    is_verified: bool
    account_status: AccountStatus
    roles: List[RoleEnum] = Field(default_factory=list)

    class Config:
        from_attributes = True
        use_enum_values = True
