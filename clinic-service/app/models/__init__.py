"""SQLAlchemy models for clinic-service internal lookups."""
import uuid

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class ClinicStaff(Base):
    __tablename__ = "clinic_staff"
    __table_args__ = {"schema": "admin"}

    staff_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    staff_role = Column(String(100), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ClinicAdmin(Base):
    __tablename__ = "clinic_admins"
    __table_args__ = {"schema": "admin"}

    clinic_admin_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
