"""Public cancellation router."""
from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import CancelAppointmentRequest, CancelAppointmentResponse
from app.services.cancellation import cancel_appointment

router = APIRouter(tags=["Cancel Appointment"])

@router.post(
    "/appointments/{appointment_id}/cancel",
    status_code=200,
    response_model=CancelAppointmentResponse,
)
def cancel_appointment_endpoint(
    request: CancelAppointmentRequest,
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("patient", "doctor", "clinic_admin", "super_admin")),
    db: Session = Depends(get_db),
) -> CancelAppointmentResponse:
    """
    Called by users to immediately drop a booked appointment returning the slot to public availability.
    """
    result = cancel_appointment(db, user=user, appointment_id=appointment_id, request=request)
    return CancelAppointmentResponse(
        appointment_id=UUID(result["appointment_id"]),
        status=result["status"],
        message=result["message"],
    )
