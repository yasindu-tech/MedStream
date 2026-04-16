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


# ---------------------------------------------------------------------------
# AS-04: Follow-up suggestions
# ---------------------------------------------------------------------------

class FollowUpSuggestRequest(BaseModel):
    original_appointment_id: UUID
    suggested_date: date
    suggested_start_time: str  # "HH:MM"
    consultation_type: str     # "physical" or "telemedicine"
    notes: Optional[str] = None


class FollowUpSuggestionResponse(BaseModel):
    suggestion_id: UUID
    original_appointment_id: UUID
    doctor_id: UUID
    doctor_name: str
    patient_id: UUID
    clinic_id: Optional[UUID]
    suggested_date: date
    suggested_start_time: str
    suggested_end_time: str
    consultation_type: str
    notes: Optional[str]
    status: str
    message: str


# ---------------------------------------------------------------------------
# AS-05: Reschedule Appointment
# ---------------------------------------------------------------------------

class RescheduleAppointmentRequest(BaseModel):
    new_date: date
    new_start_time: str  # "HH:MM"
    new_consultation_type: str


# ---------------------------------------------------------------------------
# AS-06: Cancel Appointment
# ---------------------------------------------------------------------------

class CancelAppointmentRequest(BaseModel):
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# AS-08: View Appointment History
# ---------------------------------------------------------------------------

class AppointmentListItemResponse(BaseModel):
    appointment_id: UUID
    doctor_id: UUID
    doctor_name: Optional[str]
    clinic_id: UUID
    clinic_name: Optional[str]
    patient_id: UUID
    patient_name: str
    date: date
    start_time: str
    end_time: str
    status: str
    payment_status: str
    consultation_type: str
    # prescription_id: Optional[UUID] = None
    # payment_id: Optional[UUID] = None

class AppointmentListPaginatedResponse(BaseModel):
    items: list[AppointmentListItemResponse]
    total: int
    page: int
    size: int
    has_more: bool

