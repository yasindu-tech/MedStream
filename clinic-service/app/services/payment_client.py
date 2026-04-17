import httpx
from uuid import UUID
from fastapi import HTTPException, status

from app.config import settings


def get_platform_payment_summary() -> dict:
    url = f"{settings.PAYMENT_SERVICE_URL}/internal/summaries/platform"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment service unavailable: {str(exc)}",
        )

    if response.status_code == status.HTTP_200_OK:
        try:
            return response.json()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Payment service returned invalid JSON.",
            )

    detail = response.text
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Payment service returned unexpected status: {response.status_code} - {detail}",
    )


def get_clinic_payment_summary(clinic_id: UUID) -> dict:
    url = f"{settings.PAYMENT_SERVICE_URL}/internal/summaries/clinic/{clinic_id}"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment service unavailable: {str(exc)}",
        )

    if response.status_code == status.HTTP_200_OK:
        try:
            return response.json()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Payment service returned invalid JSON.",
            )

    detail = response.text
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Payment service returned unexpected status: {response.status_code} - {detail}",
    )
