"""Pydantic schemas for telemedicine-service."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class AttendanceUpdateRequest(BaseModel):
    joined_within_grace: bool
    reason: str | None = None


class ProvisionSessionRequest(BaseModel):
    appointment_id: UUID
    consultation_type: str


class ProvisionSessionResponse(BaseModel):
    session_id: UUID
    appointment_id: UUID
    provider_name: str | None = None
    status: str
    session_version: int
    token_version: int
    created: bool


class JoinLinkRequest(BaseModel):
    appointment_id: UUID


class JoinLinkResponse(BaseModel):
    session_id: UUID
    join_url: str
    expires_in_seconds: int


class InvalidateSessionRequest(BaseModel):
    appointment_id: UUID
    reason: str | None = None


class RescheduleSessionRequest(BaseModel):
    appointment_id: UUID
    new_date: date
    new_start_time: str
    reason: str | None = None


class TelemedicineSessionSummary(BaseModel):
    session_id: UUID
    appointment_id: UUID
    status: str
    provider_name: str | None = None
    session_version: int
    token_version: int


class JoinTokenPayload(BaseModel):
    session_id: UUID
    appointment_id: UUID
    participant_role: str
    participant_user_id: UUID
    token_version: int
    session_version: int
