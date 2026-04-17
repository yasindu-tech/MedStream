"""SQLAlchemy models for telemedicine-service."""
import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class TelemedicineSession(Base):
    __tablename__ = "telemedicine_sessions"
    __table_args__ = {"schema": "patientcare"}

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    provider_name = Column(String(100), nullable=True)
    meeting_link = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="scheduled")
    session_version = Column(Integer, nullable=False, default=1)
    token_version = Column(Integer, nullable=False, default=1)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = {"schema": "patientcare"}

    appointment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), nullable=True)
    appointment_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = {"schema": "patientcare"}

    patient_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)


class TelemedicineSessionEvent(Base):
    __tablename__ = "telemedicine_session_events"
    __table_args__ = {"schema": "patientcare"}

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patientcare.telemedicine_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String(50), nullable=False)
    actor = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GoogleOAuthIntegration(Base):
    __tablename__ = "google_oauth_integrations"
    __table_args__ = {"schema": "patientcare"}

    integration_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), nullable=False, unique=True, default="google_meet")
    account_email = Column(String(255), nullable=True)
    refresh_token = Column(Text, nullable=False)
    scope = Column(Text, nullable=True)
    token_type = Column(String(50), nullable=True)
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
