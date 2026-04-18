"""Symptom chatbot router for doctor recommendations."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.middleware import require_roles
from app.schemas import ChatbotRecommendationRequest, ChatbotRecommendationResponse
from app.services.ai_client import get_chatbot_recommendations

router = APIRouter(tags=["Chatbot Recommendations"])


@router.post(
    "/chatbot/recommendations",
    response_model=ChatbotRecommendationResponse,
)
def chatbot_recommendations(
    request: ChatbotRecommendationRequest,
    user: dict = Depends(require_roles("patient")),
) -> ChatbotRecommendationResponse:
    """Single-turn symptom-to-doctor recommendation endpoint for MVP."""
    _ = user

    payload = get_chatbot_recommendations(
        symptoms=request.symptoms,
        target_date=request.target_date,
        consultation_type=request.consultation_type,
        clinic_id=request.clinic_id,
        max_recommendations=request.max_recommendations,
    )
    return ChatbotRecommendationResponse(**payload)
