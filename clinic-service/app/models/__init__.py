"""SQLAlchemy models for clinic-service internal lookups."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
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
    staff_role = Column(String(100), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Doctor(Base):
    __tablename__ = "doctors"
    __table_args__ = {"schema": "admin"}

    doctor_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String(30), nullable=False, default="active")


class DoctorClinicAssignment(Base):
    __tablename__ = "doctor_clinic_assignments"
    __table_args__ = {"schema": "admin"}

    assignment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id = Column(UUID(as_uuid=True), nullable=False)
    clinic_id = Column(UUID(as_uuid=True), nullable=False)
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
