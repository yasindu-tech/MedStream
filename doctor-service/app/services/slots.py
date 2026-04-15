"""Shared slot-generation helper used by doctor_search and doctor_profile."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from app.schemas import SlotItem


def _parse_time(t: str) -> datetime:
    """Parse 'HH:MM' into a datetime (date part is irrelevant)."""
    return datetime.strptime(t, "%H:%M")


def generate_slots(
    start: str,
    end: str,
    duration_minutes: int,
    booked_starts: set[str],
) -> List[SlotItem]:
    """
    Generate all slots between *start* and *end* at *duration_minutes*
    intervals, excluding any whose start_time appears in *booked_starts*.
    """
    slots: List[SlotItem] = []
    current = _parse_time(start)
    finish = _parse_time(end)
    delta = timedelta(minutes=duration_minutes)

    while current + delta <= finish:
        slot_start = current.strftime("%H:%M")
        slot_end = (current + delta).strftime("%H:%M")
        if slot_start not in booked_starts:
            slots.append(SlotItem(start_time=slot_start, end_time=slot_end))
        current += delta

    return slots
