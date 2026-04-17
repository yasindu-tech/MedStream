"""Pydantic schemas for the doctor service."""
from __future__ import annotations
from uuid import UUID
from typing import List, Optional, Literal
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# AS-01: Search response schemas
# ---------------------------------------------------------------------------

class SlotItem(BaseModel):
    start_time: str   # "HH:MM"
    end_time: str     # "HH:MM"


class DoctorSearchResult(BaseModel):
    doctor_id: UUID
    full_name: str
    specialization: Optional[str]
    consultation_type: Optional[str]
    clinic_id: UUID
    clinic_name: str
    consultation_fee: Optional[str] = None
    available_slots: List[SlotItem]
    has_slots: bool

    class Config:
        from_attributes = True


class DoctorSearchResponse(BaseModel):
    results: List[DoctorSearchResult]
    total: int
    empty_state: bool


# ---------------------------------------------------------------------------
# AS-02: Doctor profile response schemas
# ---------------------------------------------------------------------------

class ClinicDetail(BaseModel):
    clinic_id: UUID
    clinic_name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class AvailabilityWindow(BaseModel):
    day_of_week: str
    start_time: str
    end_time: str
    slot_duration: int
    consultation_type: Optional[str] = None


class DoctorProfileClinic(BaseModel):
    clinic: ClinicDetail
    availability: List[AvailabilityWindow]
    available_slots: List[SlotItem]   # populated when date is given
    has_slots: bool


class DoctorProfileResponse(BaseModel):
    doctor_id: UUID
    full_name: str
    specialization: Optional[str] = None
    specializations: Optional[List[str]] = None
    primary_specialization: Optional[str] = None
    bio: Optional[str] = None
    experience_years: Optional[int] = None
    qualifications: Optional[str] = None
    consultation_mode: Optional[str] = None
    medical_registration_no: Optional[str] = None
    verification_status: str
    profile_image_url: Optional[str] = None
    consultation_fee: Optional[str] = None
    profile_complete: bool
    clinics: List[DoctorProfileClinic]


class DoctorCreateRequest(BaseModel):
    user_id: UUID
    full_name: str
    medical_registration_no: Optional[str] = None
    specialization: Optional[str] = None
    specializations: Optional[List[str]] = None
    primary_specialization: Optional[str] = None
    consultation_mode: Optional[str] = None
    bio: Optional[str] = None
    experience_years: Optional[int] = None
    qualifications: Optional[str] = None
    profile_image_url: Optional[str] = None
    consultation_fee: Optional[float] = None


class DoctorUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    medical_registration_no: Optional[str] = None
    specialization: Optional[str] = None
    specializations: Optional[List[str]] = None
    primary_specialization: Optional[str] = None
    consultation_mode: Optional[str] = None
    bio: Optional[str] = None
    experience_years: Optional[int] = None
    qualifications: Optional[str] = None
    profile_image_url: Optional[str] = None
    consultation_fee: Optional[float] = None


class DoctorVisibilityRequest(BaseModel):
    visible: bool


class DoctorProfileHistoryItem(BaseModel):
    history_id: UUID
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: Optional[str] = None
    reason: Optional[str] = None
    changed_at: str


class DoctorProfileHistoryListResponse(BaseModel):
    results: List[DoctorProfileHistoryItem]
    total: int


class DoctorClinicAssignmentItem(BaseModel):
    clinic_id: UUID
    clinic_name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class DoctorClinicAssignmentListResponse(BaseModel):
    results: List[DoctorClinicAssignmentItem]
    total: int


class DoctorAvailabilityCreateRequest(BaseModel):
    clinic_id: UUID
    day_of_week: Optional[str] = None
    date: Optional[str] = None
    start_time: str
    end_time: str
    slot_duration: int
    consultation_type: Optional[str] = None


class DoctorAvailabilityUpdateRequest(BaseModel):
    day_of_week: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    slot_duration: Optional[int] = None
    consultation_type: Optional[str] = None
    status: Optional[str] = None


class DoctorAvailabilityResponse(BaseModel):
    availability_id: UUID
    clinic_id: UUID
    day_of_week: Optional[str] = None
    date: Optional[str] = None
    start_time: str
    end_time: str
    slot_duration: int
    consultation_type: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class DoctorAvailabilityListResponse(BaseModel):
    results: List[DoctorAvailabilityResponse]
    total: int


class DoctorLeaveRequest(BaseModel):
    clinic_id: Optional[UUID] = None
    start_datetime: str
    end_datetime: str
    reason: Optional[str] = None


class DoctorLeaveResponse(BaseModel):
    leave_id: UUID
    clinic_id: Optional[UUID] = None
    start_datetime: str
    end_datetime: str
    reason: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class DoctorLeaveListResponse(BaseModel):
    results: List[DoctorLeaveResponse]
    total: int


class VerificationDocumentItem(BaseModel):
    name: str
    url: str
    uploaded_at: Optional[str] = None
    status: Optional[str] = None

    class Config:
        from_attributes = True


class PendingDoctorItem(BaseModel):
    doctor_id: UUID
    full_name: str
    specialization: Optional[str] = None
    consultation_mode: Optional[str] = None
    medical_registration_no: Optional[str] = None
    verification_status: str
    status: str
    has_documents: bool
    missing_documents: bool

    class Config:
        from_attributes = True


class PendingDoctorListResponse(BaseModel):
    results: List[PendingDoctorItem]
    total: int


class DoctorVerificationDetailsResponse(BaseModel):
    doctor_id: UUID
    full_name: str
    medical_registration_no: Optional[str] = None
    verification_status: str
    status: str
    verification_documents: List[VerificationDocumentItem]
    missing_documents: bool
    verification_rejection_reason: Optional[str] = None


class DoctorVerificationActionRequest(BaseModel):
    action: Literal["approve", "reject"]
    reason: Optional[str] = None


class DoctorSuspendRequest(BaseModel):
    reason: Optional[str] = None


class DoctorVerificationActionResponse(BaseModel):
    doctor_id: UUID
    verification_status: str
    verification_rejection_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# AS-02b: Profile history schema
# ---------------------------------------------------------------------------

class DoctorProfileHistoryItem(BaseModel):
    history_id: UUID
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: Optional[str] = None
    reason: Optional[str] = None
    changed_at: str


class DoctorProfileHistoryListResponse(BaseModel):
    results: List[DoctorProfileHistoryItem]
    total: int


# ---------------------------------------------------------------------------
# AS-03: Slot validation response schema
# ---------------------------------------------------------------------------

class SlotValidationResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None
    doctor_name: Optional[str] = None
    clinic_name: Optional[str] = None
    consultation_fee: Optional[float] = None
    end_time: Optional[str] = None
    slot_duration: Optional[int] = None


# ---------------------------------------------------------------------------
# AS-04: User resolve schema
# ---------------------------------------------------------------------------

class DoctorIdResponse(BaseModel):
    doctor_id: UUID
    full_name: str

