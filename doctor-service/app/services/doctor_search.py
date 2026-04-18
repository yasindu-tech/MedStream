"""Core doctor search logic: filter, slot computation, and sorting."""
from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Doctor, Clinic, DoctorClinicAssignment, DoctorAvailability
from app.schemas import DoctorSearchResult, SlotItem
from app.services.appointment_client import get_booked_slots_batch
from app.services.slots import generate_slots


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

def search_doctors(
    db: Session,
    *,
    specialty: Optional[str] = None,
    target_date: Optional[date] = None,
    consultation_type: Optional[str] = None,
    clinic_id: Optional[UUID] = None,
) -> List[DoctorSearchResult]:
    """
    1. Query admin DB for active, verified doctors matching the filters.
    2. For each (doctor, clinic, availability) triple, compute available slots.
    3. Sort by earliest available slot; doctors with no slots go to the end.
    """

    # Determine day-of-week for availability filtering
    day_of_week: Optional[str] = None
    if target_date:
        day_of_week = target_date.strftime("%A").lower()  # e.g. "monday"

    # -----------------------------------------------------------------------
    # Base query: join Doctor → DoctorClinicAssignment → Clinic → DoctorAvailability
    # -----------------------------------------------------------------------
    query = (
        db.query(Doctor, Clinic, DoctorAvailability)
        .join(
            DoctorClinicAssignment,
            (DoctorClinicAssignment.doctor_id == Doctor.doctor_id)
            & (DoctorClinicAssignment.status == "active"),
        )
        .join(
            Clinic,
            (Clinic.clinic_id == DoctorClinicAssignment.clinic_id)
            & (Clinic.status == "active"),
        )
        .join(
            DoctorAvailability,
            (DoctorAvailability.doctor_id == Doctor.doctor_id)
            & (DoctorAvailability.clinic_id == DoctorClinicAssignment.clinic_id)
            & (DoctorAvailability.status == "active"),
        )
        .filter(
            Doctor.status == "active",
            Doctor.verification_status == "verified",
        )
    )

    # Optional filters
    if specialty:
        query = query.filter(Doctor.specialization.ilike(f"%{specialty}%"))
    if clinic_id:
        query = query.filter(Clinic.clinic_id == clinic_id)
    if consultation_type:
        query = query.filter(DoctorAvailability.consultation_type == consultation_type)
    if day_of_week:
        query = query.filter(DoctorAvailability.day_of_week == day_of_week)

    rows = query.all()

    # -----------------------------------------------------------------------
    # Slot computation
    # When a date is given  → rows are already filtered to one day_of_week,
    #                          so each (doctor, clinic) appears once → compute slots.
    # When no date is given → rows contain one row PER availability day.
    #                          Deduplicate on (doctor_id, clinic_id) and
    #                          return the doctor card with no slot data.
    # -----------------------------------------------------------------------
    results: List[DoctorSearchResult] = []

    if target_date:
        # Batch-fetch booked slots for all doctors in one HTTP call
        unique_doctor_ids = list({str(doctor.doctor_id) for doctor, _, _ in rows})
        booked_map = get_booked_slots_batch(unique_doctor_ids, target_date)

        for doctor, clinic, availability in rows:
            key = (str(doctor.doctor_id), str(clinic.clinic_id))
            booked_list = booked_map.get(key, [])
            booked_starts = {b.start_time for b in booked_list}
            slots = generate_slots(
                availability.start_time,
                availability.end_time,
                availability.slot_duration,
                booked_starts,
            )
            fee = str(doctor.consultation_fee) if doctor.consultation_fee is not None else None
            results.append(
                DoctorSearchResult(
                    doctor_id=doctor.doctor_id,
                    full_name=doctor.full_name,
                    specialization=doctor.specialization,
                    consultation_type=availability.consultation_type,
                    clinic_id=clinic.clinic_id,
                    clinic_name=clinic.clinic_name,
                    consultation_fee=fee,
                    clinic_facility_charge=float(clinic.facility_charge) if clinic.facility_charge is not None else 0.0,
                    available_slots=slots,
                    has_slots=len(slots) > 0,
                )
            )
    else:
        # No date → deduplicate: one result card per (doctor_id, clinic_id)
        seen: set[tuple] = set()
        for doctor, clinic, availability in rows:
            key = (doctor.doctor_id, clinic.clinic_id)
            if key in seen:
                continue
            seen.add(key)
            fee = str(doctor.consultation_fee) if doctor.consultation_fee is not None else None
            clinic_fee = float(clinic.facility_charge) if clinic.facility_charge is not None else 0.0
            results.append(
                DoctorSearchResult(
                    doctor_id=doctor.doctor_id,
                    full_name=doctor.full_name,
                    specialization=doctor.specialization,
                    # Use the first available row's consultation_type
                    consultation_type=availability.consultation_type,
                    clinic_id=clinic.clinic_id,
                    clinic_name=clinic.clinic_name,
                    consultation_fee=fee,
                    clinic_facility_charge=clinic_fee,
                    available_slots=[],   # no date = no slot computation
                    has_slots=False,
                )
            )

    # -----------------------------------------------------------------------
    # Sort: earliest available slot first; no-slot doctors go to the end
    # -----------------------------------------------------------------------
    def _sort_key(r: DoctorSearchResult):
        if r.available_slots:
            return (0, r.available_slots[0].start_time)
        return (1, "")

    results.sort(key=_sort_key)
    return results
