"""Public reschedule router."""
from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import RescheduleAppointmentRequest, BookAppointmentResponse
from app.services.reschedule import reschedule_appointment

router = APIRouter(tags=["Reschedule Appointment"])


@router.post("/appointments/{appointment_id}/reschedule", response_model=BookAppointmentResponse, status_code=200)
def reschedule_appointment_endpoint(
    request: RescheduleAppointmentRequest,
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
) -> BookAppointmentResponse:
    """
    Called by a patient to safely reschedule a confirmed/pending appointment bounded directly by their user_id. 
    """
    patient_user_id = user.get("sub")
    return reschedule_appointment(db, patient_user_id=patient_user_id, appointment_id=appointment_id, request=request)
