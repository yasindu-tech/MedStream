from __future__ import annotations

import datetime
import enum
import uuid

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base

class RoleEnum(str, enum.Enum):
    admin = "admin"
    doctor = "doctor"
    patient = "patient"
    staff = "staff"
    clinic_admin = "clinic_admin"
    clinic_staff = "clinic_staff"
    system_admin = "system_admin"

class AccountStatusEnum(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id = Column("user_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, unique=True, nullable=True)
    password_hash = Column(String, nullable=False)
    is_verified = Column(Boolean, nullable=False, default=False)
    account_status = Column(String, nullable=False, default=AccountStatusEnum.ACTIVE.value)
    suspension_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    roles = relationship(
        "Role",
        secondary="auth.user_roles",
        back_populates="users",
        lazy="joined",
    )
    user_roles = relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    sessions = relationship(
        "AuthSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    otps = relationship(
        "OTPVerification",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def role_names(self) -> list[str]:
        return [role.role_name for role in self.roles]

class Role(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": "auth"}

    role_id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    users = relationship(
        "User",
        secondary="auth.user_roles",
        back_populates="roles",
        lazy="selectin",
    )
    user_roles = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
        {"schema": "auth"},
    )

    user_role_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth.users.user_id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("auth.roles.role_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")

class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = {"schema": "auth"}

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth.users.user_id", ondelete="CASCADE"), nullable=False)
    refresh_token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="sessions")

class OTPVerification(Base):
    __tablename__ = "otp_verifications"
    __table_args__ = {"schema": "auth"}

    otp_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth.users.user_id", ondelete="CASCADE"), nullable=False)
    otp_code = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="otps")
