from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CreateClinicRequest(BaseModel):
    clinic_name: str = Field(..., min_length=3, description="The clinic's display name")
    registration_no: str = Field(..., min_length=3, description="Unique registration identifier")
    address: str = Field(..., min_length=10, description="Physical address of the clinic")
    phone: str = Field(..., min_length=7, max_length=30, description="Contact phone number")
    email: EmailStr = Field(..., description="Contact email address")


class ClinicResponse(BaseModel):
    clinic_id: UUID
    clinic_name: str
    registration_no: str | None
    address: str | None
    phone: str | None
    email: EmailStr | None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateClinicStatusRequest(BaseModel):
    status: Literal["active", "inactive"]
    reason: str | None = Field(None, description="Optional reason for the status change")


class ClinicActionResponse(BaseModel):
    clinic_id: UUID
    status: str
    message: str

    class Config:
        from_attributes = True
