"""Pydantic schemas for appointment-service."""
from __future__ import annotations
from datetime import date
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Internal: booked slot contract (consumed by doctor-service)
# ---------------------------------------------------------------------------

class DoctorEventRequest(BaseModel):
    event_type: str
    payload: dict


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
    status: str             # "pending_doctor", "pending_payment", or "confirmed"
    payment_status: str     # "pending" or "not_required"
    consultation_fee: Optional[float] = None
    payment_id: Optional[UUID] = None
    message: str


class AppointmentActionRequest(BaseModel):
    reason: Optional[str] = None


class AppointmentNoteRequest(BaseModel):
    content: str


class AppointmentNoteResponse(BaseModel):
    note_id: UUID
    appointment_id: UUID
    doctor_id: UUID
    content: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class MedicationItem(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    notes: Optional[str] = None


class PrescriptionRequest(BaseModel):
    medications: List[MedicationItem]
    instructions: Optional[str] = None


class PrescriptionResponse(BaseModel):
    prescription_id: UUID
    appointment_id: UUID
    doctor_id: UUID
    patient_id: UUID
    clinic_id: Optional[UUID] = None
    medications: List[MedicationItem]
    instructions: Optional[str] = None
    status: str
    issued_at: Optional[str] = None
    finalized_at: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PatientSummaryResponse(BaseModel):
    patient_id: UUID
    full_name: str
    dob: Optional[date] = None
    gender: Optional[str] = None
    nic_passport: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    blood_group: Optional[str] = None
    appointment_id: UUID
    appointment_date: date
    appointment_start_time: str
    appointment_end_time: str
    appointment_type: str
    appointment_status: str
    consultation_fee: Optional[float] = None


class PatientDocumentRequest(BaseModel):
    name: str
    document_type: Optional[str] = None
    url: str
    description: Optional[str] = None


class PatientDocumentResponse(BaseModel):
    document_id: UUID
    patient_id: UUID
    appointment_id: Optional[UUID] = None
    name: str
    document_type: Optional[str] = None
    url: str
    description: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_at: str

    class Config:
        from_attributes = True


class PatientDocumentsResponse(BaseModel):
    results: List[PatientDocumentResponse]
    total: int


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


# ---------------------------------------------------------------------------
# AS-09 / AS-10 / AS-11: Outcome, Admin, Policy
# ---------------------------------------------------------------------------

class AppointmentOutcomeResponse(BaseModel):
    appointment_id: UUID
    status: str
    changed_at: str
    message: str


class MarkNoShowRequest(BaseModel):
    reason: Optional[str] = None


class MarkArrivedRequest(BaseModel):
    reason: Optional[str] = None


class InternalNoShowRequest(BaseModel):
    reason: Optional[str] = None
    mark_by: str = "system"
    observed_join_within_grace: bool = False


class AppointmentStatusHistoryItem(BaseModel):
    history_id: UUID
    old_status: Optional[str]
    new_status: str
    changed_by: Optional[str]
    reason: Optional[str]
    changed_at: str


class AppointmentStatsResponse(BaseModel):
    total_bookings: int
    total_cancellations: int
    total_no_shows: int
    total_completed: int


class AppointmentPolicyResponse(BaseModel):
    policy_id: UUID
    cancellation_window_hours: int
    reschedule_window_hours: int
    advance_booking_days: int
    no_show_grace_period_minutes: int
    max_reschedules: int
    is_active: bool
    created_by: Optional[str]
    created_at: str
    updated_at: str


class UpdateAppointmentPolicyRequest(BaseModel):
    cancellation_window_hours: int
    reschedule_window_hours: int
    advance_booking_days: int
    no_show_grace_period_minutes: int
    max_reschedules: int
    reason: Optional[str] = None

