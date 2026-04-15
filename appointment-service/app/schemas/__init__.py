"""Pydantic schemas for appointment-service."""
from __future__ import annotations
from datetime import date
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Internal: booked slot contract (consumed by doctor-service)
# ---------------------------------------------------------------------------

class BookedSlotResponse(BaseModel):
    doctor_id: UUID
    clinic_id: UUID
    date: date
    start_time: str   # "HH:MM"
    end_time: str     # "HH:MM"

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# AS-01: Doctor search response (mirrors doctor-service contract)
# ---------------------------------------------------------------------------

class SlotItem(BaseModel):
    start_time: str
    end_time: str


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


class DoctorSearchResponse(BaseModel):
    results: List[DoctorSearchResult]
    total: int
    empty_state: bool


# ---------------------------------------------------------------------------
# AS-02: Doctor profile response (mirrors doctor-service contract)
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
    available_slots: List[SlotItem]
    has_slots: bool


class DoctorProfileResponse(BaseModel):
    doctor_id: UUID
    full_name: str
    specialization: Optional[str] = None
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


# ---------------------------------------------------------------------------
# AS-03: Booking request/response
# ---------------------------------------------------------------------------

class BookAppointmentRequest(BaseModel):
    doctor_id: UUID
    clinic_id: UUID
    date: date              # YYYY-MM-DD
    start_time: str         # "HH:MM"
    consultation_type: str  # "physical" or "telemedicine"


class BookAppointmentResponse(BaseModel):
    appointment_id: UUID
    doctor_name: str
    clinic_name: str
    date: date
    start_time: str
    end_time: str
    consultation_type: str
    status: str             # "pending_payment" or "confirmed"
    payment_status: str     # "pending" or "not_required"
    consultation_fee: Optional[float] = None
    message: str

