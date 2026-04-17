from __future__ import annotations
from typing import Optional
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.config import settings


def verify_doctor_registration(user_id: UUID) -> dict[str, str]:
    url = f"{settings.AUTH_SERVICE_URL.rstrip('/')}/internal/users/{user_id}"
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
            if data.get("account_status") != "ACTIVE":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Auth account is not active. Doctor profile may only be created after approval.",
                )
            if "doctor" not in data.get("roles", []):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Auth account does not have doctor role.",
                )
            return data
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auth user not found")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to verify auth user status",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service is unavailable. Please try again later.",
        )


def publish_doctor_event(event_type: str, payload: dict[str, str | bool | int]) -> None:
    url = f"{settings.APPOINTMENT_SERVICE_URL.rstrip('/')}/internal/doctor-events"
    body = {
        "event_type": event_type,
        "payload": payload,
    }
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(url, json=body)
    except httpx.RequestError:
        # Fail-open: dependent service update is useful but not blocking for doctor profile/save.
        return
