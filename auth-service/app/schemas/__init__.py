from pydantic import BaseModel, EmailStr
from uuid import UUID
from enum import Enum

class RoleEnum(str, Enum):
    super_admin = "super_admin"
    clinic_admin = "clinic_admin"
    doctor = "doctor"
    patient = "patient"

# --- Request Schemas ---
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    role: RoleEnum = RoleEnum.patient

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

# --- Response Schemas ---
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: UUID
    email: str
    role: RoleEnum
    is_active: bool

    class Config:
        from_attributes = True