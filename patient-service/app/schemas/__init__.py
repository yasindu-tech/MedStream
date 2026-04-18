from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class BloodGroup(str, Enum):
    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"
    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"


class PatientProfileCreate(BaseModel):
    user_id: UUID
    email: EmailStr
    phone: Optional[str] = None
    full_name: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[str] = None
    blood_group: Optional[BloodGroup] = None
    nic_passport: Optional[str] = None


class PatientProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    profile_image_url: Optional[str] = None
    nic_passport: Optional[str] = None
    blood_group: Optional[BloodGroup] = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

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
        normalized = value.strip()
        if not normalized:
            return None

        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Invalid profile image URL")

        allowed_extensions = (".jpg", ".jpeg", ".png", ".webp")
        last_segment = parsed.path.rsplit("/", 1)[-1].lower()
        if "." in last_segment and not last_segment.endswith(allowed_extensions):
            raise ValueError("Unsupported profile image format")

        return normalized


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


class PatientProfilePageResponse(BaseModel):
    patient_id: UUID
    user_id: UUID
    full_name: str
    dob: Optional[date] = None
    gender: Optional[str] = None
    nic_passport: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    blood_group: Optional[BloodGroup] = None
    profile_image_url: Optional[str] = None
    profile_status: str
    profile_completion: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class AllergyCreate(BaseModel):
    allergy_name: str
    note: Optional[str] = None

    @field_validator("allergy_name")
    @classmethod
    def validate_allergy_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Allergy name is required")
        return normalized


class AllergyUpdate(BaseModel):
    allergy_name: Optional[str] = None
    note: Optional[str] = None

    @field_validator("allergy_name")
    @classmethod
    def validate_allergy_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Allergy name is required")
        return normalized


class AllergyResponse(BaseModel):
    allergy_id: UUID
    patient_id: UUID
    allergy_name: str
    note: Optional[str] = None

    class Config:
        from_attributes = True


class ChronicConditionCreate(BaseModel):
    condition_name: str
    note: Optional[str] = None

    @field_validator("condition_name")
    @classmethod
    def validate_condition_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Condition name is required")
        return normalized


class ChronicConditionUpdate(BaseModel):
    condition_name: Optional[str] = None
    note: Optional[str] = None

    @field_validator("condition_name")
    @classmethod
    def validate_condition_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Condition name is required")
        return normalized


class ChronicConditionResponse(BaseModel):
    condition_id: UUID
    patient_id: UUID
    condition_name: str
    note: Optional[str] = None

    class Config:
        from_attributes = True


class PatientPrescriptionResponse(BaseModel):
    prescription_id: UUID
    appointment_id: UUID
    patient_id: UUID
    doctor_id: Optional[UUID] = None
    clinic_id: Optional[UUID] = None
    medications: list[dict[str, Any]]
    instructions: Optional[str] = None
    status: str
    issued_at: Optional[datetime] = None
    finalized_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MedicalDocumentUpdate(BaseModel):
    document_type: Optional[str] = None
    visibility: Optional[str] = None

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Document type is required")
        return normalized

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"public", "private", "doctor_only"}:
            raise ValueError("Visibility must be one of: public, private, doctor_only")
        return normalized


class MedicalDocumentResponse(BaseModel):
    document_id: UUID
    patient_id: UUID
    document_type: str
    file_name: str
    file_url: str
    visibility: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class InternalPatientMedicalSummaryResponse(BaseModel):
    profile: PatientProfilePageResponse
    allergies: list[AllergyResponse]
    chronic_conditions: list[ChronicConditionResponse]
    prescriptions: list[PatientPrescriptionResponse]
    documents: list[MedicalDocumentResponse]
