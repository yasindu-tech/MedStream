from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

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
