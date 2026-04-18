"""Pydantic schemas for appointment-service."""
from __future__ import annotations
from datetime import date, datetime
from uuid import UUID
from typing import List, Optional, Literal
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


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
    model_config = ConfigDict(populate_by_name=True)

    doctor_id: UUID = Field(validation_alias=AliasChoices("doctor_id", "doctorId"))
    clinic_id: UUID = Field(validation_alias=AliasChoices("clinic_id", "clinicId"))
    date: date              # YYYY-MM-DD
    start_time: str = Field(validation_alias=AliasChoices("start_time", "startTime"))         # "HH:MM"
    consultation_type: Literal["physical", "telemedicine"] = Field(validation_alias=AliasChoices("consultation_type", "consultationType"))


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


class InternalPreConsultationContextRequest(BaseModel):
    doctor_user_id: str
    recent_limit: int = 10


class PreConsultationAppointmentInfo(BaseModel):
    appointment_id: UUID
    patient_id: UUID
    doctor_id: Optional[UUID] = None
    doctor_name: Optional[str] = None
    clinic_id: Optional[UUID] = None
    clinic_name: Optional[str] = None
    appointment_date: date
    start_time: str
    end_time: str
    appointment_type: str
    appointment_status: str


class PreConsultationClinicHistoryItem(BaseModel):
    clinic_id: Optional[UUID] = None
    clinic_name: Optional[str] = None
    visit_count: int
    last_visit_date: Optional[date] = None


class PreConsultationNoteItem(BaseModel):
    note_id: UUID
    appointment_id: UUID
    doctor_id: UUID
    content: str
    created_at: str
    updated_at: str


class PreConsultationPrescriptionItem(BaseModel):
    prescription_id: UUID
    appointment_id: UUID
    patient_id: UUID
    doctor_id: Optional[UUID] = None
    clinic_id: Optional[UUID] = None
    medications: List[MedicationItem]
    instructions: Optional[str] = None
    status: str
    issued_at: Optional[str] = None
    finalized_at: Optional[str] = None
    created_at: str
    updated_at: str


class InternalPreConsultationContextResponse(BaseModel):
    patient: PatientSummaryResponse
    appointment: PreConsultationAppointmentInfo
    clinic_history: List[PreConsultationClinicHistoryItem]
    recent_notes: List[PreConsultationNoteItem]
    recent_prescriptions: List[PreConsultationPrescriptionItem]
    recent_reports: List[PatientDocumentResponse]


class InternalPostConsultationMedicationItem(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    notes: Optional[str] = None


class InternalPostConsultationNote(BaseModel):
    diagnosis: Optional[str] = None
    symptoms: Optional[str] = None
    advice: Optional[str] = None
    created_at: Optional[str] = None


class InternalPostConsultationPrescription(BaseModel):
    prescription_id: UUID
    instructions: Optional[str] = None
    status: str
    issued_at: Optional[str] = None
    medications: List[InternalPostConsultationMedicationItem] = []


class InternalPostConsultationFollowUp(BaseModel):
    suggestion_id: UUID
    suggested_date: date
    suggested_start_time: str
    consultation_type: str
    status: str
    notes: Optional[str] = None


class InternalPostConsultationPatient(BaseModel):
    patient_id: UUID
    user_id: Optional[UUID] = None
    full_name: str
    email: Optional[str] = None


class InternalPostConsultationAppointment(BaseModel):
    appointment_id: UUID
    appointment_date: date
    start_time: str
    end_time: str
    appointment_type: str
    appointment_status: str
    doctor_name: Optional[str] = None
    clinic_name: Optional[str] = None


class InternalPostConsultationContextResponse(BaseModel):
    patient: InternalPostConsultationPatient
    appointment: InternalPostConsultationAppointment
    consultation_note: InternalPostConsultationNote
    prescription: Optional[InternalPostConsultationPrescription] = None
    follow_up: Optional[InternalPostConsultationFollowUp] = None


class AIDoctorRiskFlag(BaseModel):
    severity: str
    title: str
    reason: str


class AIDoctorOverviewSection(BaseModel):
    key: str
    title: str
    summary: str
    highlights: List[str]
    source_count: int = 0
    latest_source_at: Optional[str] = None


class DoctorAIPatientOverviewResponse(BaseModel):
    appointment_id: UUID
    patient_id: UUID
    generated_at: str
    llm_used: bool
    overall_summary: str
    risk_flags: List[AIDoctorRiskFlag]
    suggested_focus_areas: List[str]
    sections: List[AIDoctorOverviewSection]


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
    consultation_type: Literal["physical", "telemedicine"]
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


class MarkTechnicalFailureRequest(BaseModel):
    reason: Optional[str] = None


class InternalNoShowRequest(BaseModel):
    reason: Optional[str] = None
    mark_by: str = "system"
    observed_join_within_grace: bool = False


class InternalTechnicalFailureRequest(BaseModel):
    reason: Optional[str] = None
    mark_by: str = "system"


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
    total_failed_sessions: int
    average_duration_minutes: Optional[float] = None


class TelemedicineLiveStatusItem(BaseModel):
    session_id: UUID
    appointment_id: UUID
    doctor_id: Optional[UUID] = None
    doctor_name: Optional[str] = None
    clinic_id: Optional[UUID] = None
    clinic_name: Optional[str] = None
    patient_id: UUID
    patient_name: str
    appointment_date: date
    start_time: str
    end_time: str
    appointment_status: str
    session_status: str
    provider_name: Optional[str] = None
    duration_minutes: Optional[float] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


class TelemedicineLiveStatusPaginatedResponse(BaseModel):
    items: list[TelemedicineLiveStatusItem]
    total: int
    page: int
    size: int
    has_more: bool


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


# ---------------------------------------------------------------------------
# Chatbot: symptom-to-doctor recommendation (MVP)
# ---------------------------------------------------------------------------

class ChatbotRecommendationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    symptoms: str
    target_date: Optional[date] = None
    consultation_type: Optional[str] = None
    clinic_id: Optional[UUID] = None
    max_recommendations: int = 5

    @model_validator(mode="before")
    @classmethod
    def _normalize_aliases(cls, data):
        if not isinstance(data, dict):
            return data

        normalized = dict(data)

        if "symptoms" not in normalized:
            for key in ("symptom", "symptom_text", "symptomText", "message", "input", "query"):
                if key in normalized:
                    normalized["symptoms"] = normalized[key]
                    break

        if "consultation_type" not in normalized and "consultationType" in normalized:
            normalized["consultation_type"] = normalized["consultationType"]

        if "clinic_id" not in normalized and "clinicId" in normalized:
            normalized["clinic_id"] = normalized["clinicId"]

        if "max_recommendations" not in normalized and "maxRecommendations" in normalized:
            normalized["max_recommendations"] = normalized["maxRecommendations"]

        if "target_date" not in normalized:
            for key in ("appointmentDate", "targetDate"):
                if key in normalized:
                    normalized["target_date"] = normalized[key]
                    break
        if "target_date" not in normalized and "date" in normalized:
            normalized["target_date"] = normalized["date"]

        return normalized

    @field_validator("symptoms")
    @classmethod
    def _validate_symptoms(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("symptoms cannot be empty")
        return normalized

    @field_validator("target_date", mode="before")
    @classmethod
    def _normalize_date(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            if "T" in raw:
                try:
                    return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
                except ValueError:
                    return value
        return value


class ChatbotRecommendationResponse(BaseModel):
    recommendation_reason: str
    suggested_specialties: List[str]
    top_doctors: List[DoctorSearchResult]
    follow_up_question: Optional[str] = None
    no_results_guidance: Optional[str] = None
    total: int
    empty_state: bool
    llm_used: bool
