"""SQLAlchemy models for the patientcare schema (appointment-service)."""
import uuid
from datetime import date, time
from sqlalchemy import Column, String, Date, Time, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = {"schema": "patientcare"}

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
