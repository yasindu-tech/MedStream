"""Internal telemedicine callbacks for appointment no-show automation."""
from __future__ import annotations

import os
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(tags=["internal"])


class AttendanceUpdateRequest(BaseModel):
    joined_within_grace: bool
    reason: str | None = None


@router.post("/appointments/{appointment_id}/attendance")
def report_attendance(appointment_id: UUID, request: AttendanceUpdateRequest) -> dict:
    appointment_service_url = os.getenv("APPOINTMENT_SERVICE_URL", "http://appointment-service:8000")

    if request.joined_within_grace:
        endpoint = f"{appointment_service_url}/internal/appointments/{appointment_id}/mark-arrived"
        payload = {"reason": request.reason or "Patient joined telemedicine session within grace period"}
    else:
        endpoint = f"{appointment_service_url}/internal/appointments/{appointment_id}/mark-no-show"
        payload = {
            "reason": request.reason or "Patient did not join telemedicine session within grace period",
            "mark_by": "system",
            "observed_join_within_grace": False,
        }

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            return {
                "appointment_id": str(appointment_id),
                "forwarded": True,
                "result": response.json(),
            }
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to update appointment outcome from telemedicine workflow: {exc}",
        )
