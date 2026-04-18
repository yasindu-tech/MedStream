from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.config import settings


def queue_clinic_admin_onboarding_email(
    user_id: UUID,
    email: str,
    clinic_name: str,
    temporary_password: str,
) -> None:
    url = f"{settings.NOTIFICATION_SERVICE_URL}/api/notifications/events"
    payload = {
        "event_type": "clinic.admin.onboarding",
        "user_id": str(user_id),
        "payload": {
            "clinic_name": clinic_name,
            "login_email": email,
            "temporary_password": temporary_password,
            "login_url": settings.LOGIN_URL,
            "email": email,
        },
        "channels": ["email"],
        "priority": "normal",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Notification service unavailable: {str(exc)}",
        )

    if response.status_code not in (status.HTTP_200_OK, status.HTTP_201_CREATED):
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to queue onboarding email: {detail}",
        )


def queue_clinic_staff_onboarding_email(
    user_id: UUID,
    email: str,
    clinic_name: str,
    temporary_password: str,
) -> None:
    url = f"{settings.NOTIFICATION_SERVICE_URL}/api/notifications/events"
    payload = {
        "event_type": "clinic.staff.onboarding",
        "user_id": str(user_id),
        "payload": {
            "clinic_name": clinic_name,
            "login_email": email,
            "temporary_password": temporary_password,
            "login_url": settings.LOGIN_URL,
            "email": email,
        },
        "channels": ["email"],
        "priority": "normal",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Notification service unavailable: {str(exc)}",
        )

    if response.status_code not in (status.HTTP_200_OK, status.HTTP_201_CREATED):
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to queue onboarding email: {detail}",
        )


def queue_doctor_onboarding_email(
    user_id: UUID,
    email: str,
    full_name: str,
    temporary_password: str,
) -> None:
    url = f"{settings.NOTIFICATION_SERVICE_URL}/api/notifications/events"
    payload = {
        "event_type": "doctor.onboarding",
        "user_id": str(user_id),
        "payload": {
            "doctor_name": full_name,
            "login_email": email,
            "temporary_password": temporary_password,
            "login_url": settings.LOGIN_URL,
            "email": email,
        },
        "channels": ["email"],
        "priority": "normal",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Notification service unavailable: {str(exc)}",
        )

    if response.status_code not in (status.HTTP_200_OK, status.HTTP_201_CREATED):
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to queue doctor onboarding email: {detail}",
        )

