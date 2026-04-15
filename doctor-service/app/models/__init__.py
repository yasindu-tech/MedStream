"""SQLAlchemy models for the admin schema (doctor-service reads from medstream_admin)."""
import uuid
from sqlalchemy import Column, String, Integer, Numeric, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
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
    consultation_mode = Column(String(40), nullable=True)
    verification_status = Column(String(30), nullable=False, default="verified")
    status = Column(String(30), nullable=False, default="active")
    bio = Column(Text, nullable=True)
    experience_years = Column(Integer, nullable=True)
    qualifications = Column(Text, nullable=True)
    profile_image_url = Column(Text, nullable=True)
    consultation_fee = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Clinic(Base):
    __tablename__ = "clinics"
    __table_args__ = {"schema": "admin"}

    clinic_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_name = Column(String(255), nullable=False)
    registration_no = Column(String(120), nullable=True)
    address = Column(String, nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(255), nullable=True)
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
    day_of_week = Column(String(20), nullable=False)   # e.g. "monday"
    start_time = Column(String(20), nullable=False)    # e.g. "09:00"
    end_time = Column(String(20), nullable=False)      # e.g. "13:00"
    slot_duration = Column(Integer, nullable=False)    # minutes
    consultation_type = Column(String(40), nullable=True)
    status = Column(String(30), nullable=False, default="active")
