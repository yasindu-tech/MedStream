"""Pydantic schemas for the doctor search response."""
from __future__ import annotations
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel


class SlotItem(BaseModel):
    start_time: str   # "HH:MM"
    end_time: str     # "HH:MM"


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

    class Config:
        from_attributes = True


class DoctorSearchResponse(BaseModel):
    results: List[DoctorSearchResult]
    total: int
    empty_state: bool
