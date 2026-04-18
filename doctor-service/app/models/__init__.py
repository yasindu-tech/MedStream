"""SQLAlchemy models for the admin schema (doctor-service reads from medstream_admin)."""
import uuid
from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base


class Doctor(Base):
    __tablename__ = "doctors"
    __table_args__ = {"schema": "admin"}

    doctor_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    full_name = Column(String(255), nullable=False)
    medical_registration_no = Column(String(120), nullable=True)
    specialization = Column(String(120), nullable=True)
    specializations = Column(JSON, nullable=True)
    primary_specialization = Column(String(120), nullable=True)
    consultation_mode = Column(String(40), nullable=True)
    verification_status = Column(String(30), nullable=False, default="verified")
    status = Column(String(30), nullable=False, default="active")
    verification_documents = Column(JSONB, nullable=True)
    verification_rejection_reason = Column(Text, nullable=True)
    suspension_reason = Column(Text, nullable=True)
    bio = Column(Text, nullable=True)
    experience_years = Column(Integer, nullable=True)
    qualifications = Column(Text, nullable=True)
    profile_image_url = Column(Text, nullable=True)
    consultation_fee = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DoctorProfileHistory(Base):
    __tablename__ = "doctor_profile_history"
    __table_args__ = {"schema": "admin"}

    history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id = Column(UUID(as_uuid=True), nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by = Column(String(100), nullable=True)
    reason = Column(Text, nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())


class Clinic(Base):
    __tablename__ = "clinics"
    __table_args__ = {"schema": "admin"}

    clinic_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_name = Column(String(255), nullable=False)
    registration_no = Column(String(120), nullable=True)
    address = Column(String, nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(255), nullable=True)
    facility_charge = Column(Numeric(10, 2), nullable=True, default=0)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DoctorClinicAssignment(Base):
    __tablename__ = "doctor_clinic_assignments"
    __table_args__ = {"schema": "admin"}

    assignment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id = Column(UUID(as_uuid=True), nullable=False)
    clinic_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(String(30), nullable=False, default="active")


class DoctorAvailability(Base):
    __tablename__ = "doctor_availability"
    __table_args__ = {"schema": "admin"}

    availability_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id = Column(UUID(as_uuid=True), nullable=False)
    clinic_id = Column(UUID(as_uuid=True), nullable=False)
    day_of_week = Column(String(20), nullable=True)   # e.g. "monday" for recurring schedule
    date = Column(Date, nullable=True)                 # one-time special availability
    start_time = Column(String(20), nullable=False)    # e.g. "09:00"
    end_time = Column(String(20), nullable=False)      # e.g. "13:00"
    slot_duration = Column(Integer, nullable=False)    # minutes
    consultation_type = Column(String(40), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DoctorAvailabilityHistory(Base):
    __tablename__ = "doctor_availability_history"
    __table_args__ = {"schema": "admin"}

    history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    availability_id = Column(UUID(as_uuid=True), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(50), nullable=False)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    changed_by = Column(String(100), nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())


class DoctorLeave(Base):
    __tablename__ = "doctor_leave"
    __table_args__ = {"schema": "admin"}

    leave_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id = Column(UUID(as_uuid=True), nullable=False)
    clinic_id = Column(UUID(as_uuid=True), nullable=True)
    start_datetime = Column(DateTime(timezone=True), nullable=False)
    end_datetime = Column(DateTime(timezone=True), nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
