"""Public follow-up router — accessible via the gateway.
POST /appointments/follow-ups/suggest
POST /appointments/follow-ups/{suggestion_id}/confirm
GET  /appointments/follow-ups/pending
"""
from __future__ import annotations
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import FollowUpSuggestRequest, FollowUpSuggestionResponse, BookAppointmentResponse
from app.services.followup import suggest_followup, confirm_followup, get_pending_followups

router = APIRouter(tags=["Follow-ups"], prefix="/appointments")


@router.post("/follow-ups/suggest", response_model=FollowUpSuggestionResponse, status_code=201)
def suggest_followup_endpoint(
    request: FollowUpSuggestRequest,
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> FollowUpSuggestionResponse:
    """
    Called by a doctor to suggest a follow-up appointment.
    """
    doctor_user_id = user.get("sub")
    return suggest_followup(db, doctor_user_id=doctor_user_id, request=request)


@router.get("/follow-ups/pending", response_model=List[FollowUpSuggestionResponse])
def get_pending_followups_endpoint(
    user: dict = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
) -> List[FollowUpSuggestionResponse]:
    """
    Fetch all 'pending' follow-up suggestions for the logged-in patient.
    """
    patient_user_id = user.get("sub")
    return get_pending_followups(db, patient_user_id=patient_user_id)


@router.post("/follow-ups/{suggestion_id}/confirm", response_model=BookAppointmentResponse)
def confirm_followup_endpoint(
    suggestion_id: UUID = Path(...),
    user: dict = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
) -> dict:  # Returning dict here since book_appointment usually returns a model, FastAPI will automatically serialize it
    """
    Called by a patient to confirm a follow-up appointment suggestion.
    """
    patient_user_id = user.get("sub")
    return confirm_followup(db, patient_user_id=patient_user_id, suggestion_id=suggestion_id)
