from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from sqlalchemy import JSON, Boolean, Column, Date, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


def _default_full_name(email: str) -> str:
    local_part = email.split("@", 1)[0]
    parts = re.split(r"[._\-]+", local_part)
    full_name = " ".join(part.capitalize() for part in parts if part)
    return full_name or "Patient"


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = {"schema": "patientcare"}

    patient_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    full_name = Column(String(255), nullable=False, default="Patient")
    dob = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)
    nic_passport = Column(String(50), nullable=True)
    phone = Column(String(30), nullable=True)
    address = Column(String, nullable=True)
    emergency_contact = Column(String(255), nullable=True)
    profile_image_url = Column(String, nullable=True)
    pending_email = Column(String(255), nullable=True)
    blood_group = Column(String(10), nullable=True)
    profile_status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    @property
    def profile_completion(self) -> int:
        profile_fields = [
            self.email,
            self.full_name,
            self.dob,
            self.gender,
            self.nic_passport,
            self.phone,
            self.address,
            self.emergency_contact,
            self.blood_group,
            self.profile_image_url,
        ]
        filled = sum(1 for value in profile_fields if value)
        total = len(profile_fields)
        return int(round((filled / total) * 100)) if total else 0

    @classmethod
    def build_full_name(cls, email: str) -> str:
        return _default_full_name(email)


class Allergy(Base):
    __tablename__ = "allergies"
    __table_args__ = {"schema": "patientcare"}

    allergy_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    allergy_name = Column(String(255), nullable=False)
    note = Column(String, nullable=True)


class ChronicCondition(Base):
    __tablename__ = "chronic_conditions"
    __table_args__ = {"schema": "patientcare"}

    condition_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    condition_name = Column(String(255), nullable=False)
    note = Column(String, nullable=True)


class Prescription(Base):
    __tablename__ = "prescriptions"
    __table_args__ = {"schema": "patientcare"}

    prescription_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(UUID(as_uuid=True), nullable=False)
    patient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    doctor_id = Column(UUID(as_uuid=True), nullable=True)
    clinic_id = Column(UUID(as_uuid=True), nullable=True)
    medications = Column(JSON, nullable=False, default=list)
    instructions = Column("notes", Text, nullable=True)
    status = Column(String(30), nullable=False, default="draft")
    issued_at = Column(DateTime(timezone=True), nullable=True)
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class MedicalDocument(Base):
    __tablename__ = "medical_documents"
    __table_args__ = {"schema": "patientcare"}

    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    document_type = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=False)
    visibility = Column(String(30), nullable=False, default="public")
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ConsultationSummary(Base):
    __tablename__ = "consultation_summaries"
    __table_args__ = {"schema": "patientcare"}

    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    patient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="generated")
    llm_used = Column(Boolean, nullable=False, default=False)
    doctor_name = Column(String(255), nullable=True)
    diagnosis = Column(Text, nullable=True)
    medications = Column(JSON, nullable=False, default=list)
    sections = Column(JSON, nullable=False, default=list)
    summary_text = Column(Text, nullable=False)
    summary_html = Column(Text, nullable=False)
    missing_fields = Column(JSON, nullable=False, default=list)
    warnings = Column(JSON, nullable=False, default=list)
    generated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
