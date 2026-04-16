"""Helpers for clinic-scoped authorization using clinic-service internal APIs."""
from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.config import settings


def resolve_staff_clinic_id(user_id: str) -> UUID:
    url = f"{settings.CLINIC_SERVICE_URL}/internal/staff/{user_id}/clinic"
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            if response.status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff user is not assigned to a clinic")
            response.raise_for_status()
            payload = response.json()
            return UUID(payload["clinic_id"])
    except HTTPException:
        raise
    except (httpx.RequestError, httpx.HTTPStatusError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to validate clinic scope at this time",
        )
