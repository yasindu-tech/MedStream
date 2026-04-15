"""Pydantic schemas for appointment-service."""
from __future__ import annotations
from datetime import date
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Internal: booked slot contract (consumed by doctor-service)
# ---------------------------------------------------------------------------

class BookedSlotResponse(BaseModel):
    doctor_id: UUID
    clinic_id: UUID
    date: date
    start_time: str   # "HH:MM"
    end_time: str     # "HH:MM"

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Public: doctor search response (mirrors doctor-service contract)
# ---------------------------------------------------------------------------

class SlotItem(BaseModel):
    start_time: str
    end_time: str


class DoctorSearchResult(BaseModel):
    doctor_id: UUID
    full_name: str
    specialization: Optional[str]
    consultation_type: Optional[str]
    clinic_id: UUID
    clinic_name: str
    consultation_fee: Optional[float] = None
    available_slots: List[SlotItem]
    has_slots: bool


class DoctorSearchResponse(BaseModel):
    results: List[DoctorSearchResult]
    total: int
    empty_state: bool
