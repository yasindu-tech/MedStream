"""SQLAlchemy models for clinic-service internal lookups."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class Clinic(Base):
    __tablename__ = "clinics"
    __table_args__ = {"schema": "admin"}

    clinic_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_name = Column(String(255), nullable=False)
    registration_no = Column(String(120), nullable=True, index=True)
    address = Column(Text, nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="inactive")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ClinicAdmin(Base):
    __tablename__ = "clinic_admins"
    __table_args__ = {"schema": "admin"}

    clinic_admin_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admin.clinics.clinic_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(String(30), nullable=False, default="pending")
    assigned_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ClinicStaff(Base):
    __tablename__ = "clinic_staff"
    __table_args__ = {"schema": "admin"}

    staff_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admin.clinics.clinic_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), nullable=True)
    staff_email = Column(String(255), nullable=True, index=True)
    staff_name = Column(String(255), nullable=True)
    staff_phone = Column(String(30), nullable=True)
    staff_role = Column(String(100), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
    updated_by = Column(String(100), nullable=True)


class ClinicStaffHistory(Base):
    __tablename__ = "clinic_staff_history"
    __table_args__ = {"schema": "admin"}

    history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = Column(UUID(as_uuid=True), nullable=False)
    clinic_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    staff_email = Column(String(255), nullable=True)
    staff_name = Column(String(255), nullable=True)
    staff_phone = Column(String(30), nullable=True)
    staff_role = Column(String(100), nullable=True)
    status = Column(String(30), nullable=False)
    action = Column(String(50), nullable=False)
    changed_by = Column(String(100), nullable=True)
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


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
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


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
    day_of_week = Column(String(20), nullable=False)
    start_time = Column(String(10), nullable=False)
    end_time = Column(String(10), nullable=False)
    slot_duration = Column(Integer, nullable=False, default=30)
    consultation_type = Column(String(40), nullable=True)
    status = Column(String(30), nullable=False, default="active")


class ClinicStatusHistory(Base):
    __tablename__ = "clinic_status_history"
    __table_args__ = {"schema": "admin"}

    history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id = Column(UUID(as_uuid=True), nullable=False)
    old_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    changed_by = Column(String(100), nullable=True)
    reason = Column(Text, nullable=True)
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
