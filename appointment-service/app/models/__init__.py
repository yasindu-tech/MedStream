"""SQLAlchemy models for the patientcare schema (appointment-service)."""
import uuid
from datetime import date, time
from sqlalchemy import Column, String, Date, Time, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
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
    clinic_id = Column(UUID(as_uuid=True), nullable=True)
    appointment_type = Column(String(50), nullable=False)
    appointment_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(String(30), nullable=False, default="scheduled")
    payment_status = Column(String(30), nullable=False, default="pending")
    cancellation_reason = Column(String, nullable=True)
    cancelled_by = Column(String(30), nullable=True)
    rescheduled_from_date = Column(Date, nullable=True)
    rescheduled_from_start_time = Column(Time, nullable=True)
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
