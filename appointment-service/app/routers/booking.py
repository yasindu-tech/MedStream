"""Public booking router — patient-facing.

Accessible via the API gateway at:
  POST /appointments/appointments/book

Requires a valid JWT with role = patient.
"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import BookAppointmentRequest, BookAppointmentResponse
from app.services.booking import book_appointment

router = APIRouter(tags=["Booking"])


@router.post("/appointments/book", response_model=BookAppointmentResponse, status_code=201)
def create_booking(
    request: BookAppointmentRequest,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    user: dict = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
) -> BookAppointmentResponse:
    """
    Book an appointment with a doctor.

    The system:
    1. Validates the slot is still available via doctor-service
    2. Checks for double-booking collisions
    3. Creates the appointment record
    4. If consultation fee > 0: status = pending_payment (TODO: payment integration)
    5. If no fee: status = confirmed (TODO: notification integration)

    Supports idempotent requests via the X-Idempotency-Key header.
    """
    patient_id = user.get("sub")  # JWT subject = user UUID

    return book_appointment(
        db,
        patient_id=patient_id,
        request=request,
        idempotency_key=x_idempotency_key,
    )
