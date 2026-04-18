"""Internal client for calling ai-service from appointment-service."""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.config import settings


def get_chatbot_recommendations(
    *,
    symptoms: str,
    target_date: Optional[date],
    consultation_type: Optional[str],
    clinic_id: Optional[UUID],
    max_recommendations: int,
) -> dict:
    url = f"{settings.AI_SERVICE_URL}/internal/chatbot/recommendations"
    headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    payload = {
        "symptoms": symptoms,
        "target_date": target_date.isoformat() if target_date else None,
        "consultation_type": consultation_type,
        "clinic_id": str(clinic_id) if clinic_id else None,
        "max_recommendations": max_recommendations,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service returned an error: {exc.response.status_code}",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is currently unavailable. Please try again later.",
        )


def get_doctor_ai_overview(*, appointment_id: UUID, doctor_user_id: str) -> dict:
    url = f"{settings.AI_SERVICE_URL}/internal/doctor/patient-overview"
    headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
    payload = {
        "appointment_id": str(appointment_id),
        "doctor_user_id": doctor_user_id,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403, 404}:
            detail = exc.response.text or "AI overview request rejected"
            raise HTTPException(status_code=exc.response.status_code, detail=detail)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service returned an error: {exc.response.status_code}",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is currently unavailable. Please try again later.",
        )


def get_post_consultation_summary(*, appointment_id: UUID) -> dict:
    url = f"{settings.AI_SERVICE_URL}/internal/post-consultation-summary"
    headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
    payload = {"appointment_id": str(appointment_id)}

    try:
        with httpx.Client(timeout=45.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service returned an error: {exc.response.status_code}",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is currently unavailable. Please try again later.",
        )
