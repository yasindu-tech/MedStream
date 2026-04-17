from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from sqlalchemy import Column, Date, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


def _default_full_name(email: str) -> str:
    local_part = email.split("@", 1)[0]
    parts = re.split(r"[._\-]+", local_part)
    full_name = " ".join(part.capitalize() for part in parts if part)
    return full_name or "Patient"


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = {"schema": "patientcare"}

    patient_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    full_name = Column(String(255), nullable=False, default="Patient")
    dob = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)
    nic_passport = Column(String(50), nullable=True)
    phone = Column(String(30), nullable=True)
    address = Column(String, nullable=True)
    blood_group = Column(String(10), nullable=True)
    profile_status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    @classmethod
    def build_full_name(cls, email: str) -> str:
        return _default_full_name(email)
