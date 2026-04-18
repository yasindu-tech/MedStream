from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


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
    available_slots: list[SlotItem]
    has_slots: bool


class ChatbotRecommendationInternalRequest(BaseModel):
    symptoms: str
    target_date: Optional[date] = None
    consultation_type: Optional[str] = None
    clinic_id: Optional[UUID] = None
    max_recommendations: int = 5


class ChatbotRecommendationInternalResponse(BaseModel):
    recommendation_reason: str
    suggested_specialties: list[str]
    top_doctors: list[DoctorSearchResult]
    follow_up_question: Optional[str] = None
    no_results_guidance: Optional[str] = None
    total: int
    empty_state: bool
    llm_used: bool


class DoctorPatientOverviewRequest(BaseModel):
    appointment_id: UUID
    doctor_user_id: str


class DoctorPatientOverviewRiskFlag(BaseModel):
    severity: str
    title: str
    reason: str


class DoctorPatientOverviewSection(BaseModel):
    key: str
    title: str
    summary: str
    highlights: list[str]
    source_count: int = 0
    latest_source_at: Optional[str] = None


class DoctorPatientOverviewResponse(BaseModel):
    appointment_id: UUID
    patient_id: UUID
    generated_at: str
    llm_used: bool
    overall_summary: str
    risk_flags: list[DoctorPatientOverviewRiskFlag]
    suggested_focus_areas: list[str]
    sections: list[DoctorPatientOverviewSection]


class PostConsultationSummaryRequest(BaseModel):
    appointment_id: UUID


class PostConsultationMedicationItem(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    notes: Optional[str] = None


class PostConsultationSection(BaseModel):
    key: str
    title: str
    content: str


class PostConsultationSummaryResponse(BaseModel):
    appointment_id: UUID
    patient_id: UUID
    patient_user_id: Optional[str] = None
    patient_email: Optional[str] = None
    patient_name: str
    doctor_name: Optional[str] = None
    generated_at: str
    status: str
    llm_used: bool
    email_eligible: bool
    missing_fields: list[str] = []
    diagnosis: Optional[str] = None
    medications: list[PostConsultationMedicationItem] = []
    sections: list[PostConsultationSection] = []
    summary_text: str
    summary_html: str
    warnings: list[str] = []
