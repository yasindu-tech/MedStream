from typing import Optional

import httpx
from fastapi import HTTPException, status

from app.config import settings


def register_clinic_admin_user(
    email: str,
    password: str,
    phone: Optional[str] = None,
) -> dict:
    payload = {
        "email": email,
        "password": password,
        "role": "clinic_admin",
    }
    if phone:
        payload["phone"] = phone

    url = f"{settings.AUTH_SERVICE_URL}/internal/clinic-admin"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Auth service unavailable: {str(exc)}",
        )

    if response.status_code == status.HTTP_201_CREATED:
        return response.json()

    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text

    if response.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT):
        raise HTTPException(status_code=response.status_code, detail=detail)

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Auth service returned unexpected status: {response.status_code} - {detail}",
    )


def deactivate_clinic_admin_user(user_id: str) -> None:
    url = f"{settings.AUTH_SERVICE_URL}/internal/clinic-admin/{user_id}/deactivate"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Auth service unavailable: {str(exc)}",
        )

    if response.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT):
        return

    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Auth service returned unexpected status: {response.status_code} - {detail}",
    )


def register_clinic_staff_user(
    email: str,
    password: str,
    phone: Optional[str] = None,
) -> dict:
    payload = {
        "email": email,
        "password": password,
        "role": "clinic_staff",
    }
    if phone:
        payload["phone"] = phone

    url = f"{settings.AUTH_SERVICE_URL}/internal/clinic-staff"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Auth service unavailable: {str(exc)}",
        )

    if response.status_code == status.HTTP_201_CREATED:
        return response.json()

    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text

    if response.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT):
        raise HTTPException(status_code=response.status_code, detail=detail)

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Auth service returned unexpected status: {response.status_code} - {detail}",
    )


def deactivate_clinic_staff_user(user_id: str) -> None:
    url = f"{settings.AUTH_SERVICE_URL}/internal/clinic-staff/{user_id}/deactivate"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Auth service unavailable: {str(exc)}",
        )

    if response.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT):
        return

    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Auth service returned unexpected status: {response.status_code} - {detail}",
    )
