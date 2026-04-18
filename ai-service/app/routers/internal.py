from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import settings
from app.schemas import (
    ChatbotRecommendationInternalRequest,
    ChatbotRecommendationInternalResponse,
    DoctorPatientOverviewRequest,
    DoctorPatientOverviewResponse,
)
from app.services.overview import generate_doctor_patient_overview
from app.services.recommendation import recommend_doctors_from_symptoms

router = APIRouter(tags=["Internal Chatbot"])


def _require_internal_service_auth(
    x_internal_service_token: str | None = Header(default=None, alias="X-Internal-Service-Token"),
) -> None:
    if x_internal_service_token != settings.INTERNAL_SERVICE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal service token",
        )


@router.post(
    "/chatbot/recommendations",
    response_model=ChatbotRecommendationInternalResponse,
)
def chatbot_recommendations_internal(
    request: ChatbotRecommendationInternalRequest,
    _: None = Depends(_require_internal_service_auth),
) -> ChatbotRecommendationInternalResponse:
    payload = recommend_doctors_from_symptoms(
        symptoms=request.symptoms,
        target_date=request.target_date,
        consultation_type=request.consultation_type,
        clinic_id=request.clinic_id,
        max_recommendations=request.max_recommendations,
    )
    return ChatbotRecommendationInternalResponse(**payload)


@router.post(
    "/doctor/patient-overview",
    response_model=DoctorPatientOverviewResponse,
)
def doctor_patient_overview_internal(
    request: DoctorPatientOverviewRequest,
    _: None = Depends(_require_internal_service_auth),
) -> DoctorPatientOverviewResponse:
    payload = generate_doctor_patient_overview(
        appointment_id=request.appointment_id,
        doctor_user_id=request.doctor_user_id,
    )
    return DoctorPatientOverviewResponse(**payload)
