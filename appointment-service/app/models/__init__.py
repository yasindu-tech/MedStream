"""SQLAlchemy models for the patientcare schema (appointment-service)."""
import uuid
from datetime import date, time
from sqlalchemy import Boolean, Column, Integer, String, Date, Time, DateTime, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.sql import func
from app.database import Base


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = {"schema": "patientcare"}

    patient_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    full_name = Column(String(255), nullable=False)
    dob = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)
    nic_passport = Column(String(50), nullable=True)
    phone = Column(String(30), nullable=True)
    address = Column(String, nullable=True)
    blood_group = Column(String(10), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint("patient_id", "idempotency_key", name="uq_appointments_patient_idempotency"),
        {"schema": "patientcare"},
    )

    appointment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_appointment_id = Column(UUID(as_uuid=True), nullable=True)
    patient_id = Column(UUID(as_uuid=True), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), nullable=True)
    doctor_name = Column(String(150), nullable=True)
    clinic_id = Column(UUID(as_uuid=True), nullable=True)
    clinic_name = Column(String(150), nullable=True)
    appointment_type = Column(String(50), nullable=False)
    appointment_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(String(30), nullable=False, default="scheduled")
    payment_status = Column(String(30), nullable=False, default="pending")
    completed_at = Column(DateTime(timezone=True), nullable=True)
    completed_by = Column(String(100), nullable=True)
    no_show_at = Column(DateTime(timezone=True), nullable=True)
    no_show_marked_by = Column(String(100), nullable=True)
    cancellation_reason = Column(String, nullable=True)
    cancelled_by = Column(String(30), nullable=True)
    rescheduled_from_date = Column(Date, nullable=True)
    rescheduled_from_start_time = Column(Time, nullable=True)
    reschedule_count = Column(Integer, nullable=False, default=0)
    policy_id = Column(UUID(as_uuid=True), nullable=True)
    idempotency_key = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FollowUpSuggestion(Base):
    __tablename__ = "follow_up_suggestions"
    __table_args__ = {"schema": "patientcare"}

    suggestion_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_appointment_id = Column(UUID(as_uuid=True), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), nullable=False)
    patient_id = Column(UUID(as_uuid=True), nullable=False)
    clinic_id = Column(UUID(as_uuid=True), nullable=True)
    suggested_date = Column(Date, nullable=False)
    suggested_start_time = Column(Time, nullable=False)
    suggested_end_time = Column(Time, nullable=False)
    consultation_type = Column(String(50), nullable=False)
    notes = Column(String, nullable=True)
    status = Column(String(30), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AppointmentStatusHistory(Base):
    __tablename__ = "appointment_status_history"
    __table_args__ = {"schema": "patientcare"}

    history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(UUID(as_uuid=True), nullable=False)
    old_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    changed_by = Column(String(100), nullable=True)
    reason = Column(String, nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())


class AppointmentNote(Base):
    __tablename__ = "appointment_notes"
    __table_args__ = {"schema": "patientcare"}

    note_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(UUID(as_uuid=True), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Prescription(Base):
    __tablename__ = "prescriptions"
    __table_args__ = {"schema": "patientcare"}

    prescription_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(UUID(as_uuid=True), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), nullable=False)
    patient_id = Column(UUID(as_uuid=True), nullable=False)
    clinic_id = Column(UUID(as_uuid=True), nullable=True)
    medications = Column(JSON, nullable=False)
    instructions = Column("notes", Text, nullable=True)
    status = Column(String(30), nullable=False, default="draft")
    issued_at = Column(DateTime(timezone=True), nullable=True)
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PatientDocument(Base):
    __tablename__ = "medical_documents"
    __table_args__ = {"schema": "patientcare"}

    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), nullable=False)
    appointment_id = Column(UUID(as_uuid=True), nullable=True)
    name = Column("file_name", String(255), nullable=False)
    document_type = Column(String(100), nullable=True)
    url = Column("file_url", Text, nullable=False)
    description = Column(Text, nullable=True)
    uploaded_by = Column(String(50), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    visibility = Column(String(50), nullable=True)


class AppointmentPolicy(Base):
    __tablename__ = "appointment_policies"
    __table_args__ = {"schema": "patientcare"}

    policy_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cancellation_window_hours = Column(Integer, nullable=False)
    reschedule_window_hours = Column(Integer, nullable=False)
    advance_booking_days = Column(Integer, nullable=False)
    no_show_grace_period_minutes = Column(Integer, nullable=False)
    max_reschedules = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AppointmentPolicyHistory(Base):
    __tablename__ = "appointment_policy_history"
    __table_args__ = {"schema": "patientcare"}

    history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    old_policy_id = Column(UUID(as_uuid=True), nullable=True)
    new_policy_id = Column(UUID(as_uuid=True), nullable=False)
    changed_by = Column(String(100), nullable=True)
    reason = Column(String, nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
