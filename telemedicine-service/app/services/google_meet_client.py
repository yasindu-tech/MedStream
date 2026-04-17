"""Google Meet link creation via Meet API spaces.create."""
from __future__ import annotations

from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.services.google_oauth import get_google_access_token_from_refresh

GOOGLE_MEET_SPACES_ENDPOINT = "https://meet.googleapis.com/v2/spaces"


def create_google_meet_link(db: Session, *, appointment_id: UUID) -> str:
    access_token = get_google_access_token_from_refresh(db)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "config": {
            "accessType": "TRUSTED",
            "entryPointAccess": "ALL",
        }
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.post(GOOGLE_MEET_SPACES_ENDPOINT, headers=headers, json=payload)

    if response.status_code >= 400:
        raise RuntimeError(
            f"Google Meet spaces.create failed for appointment {appointment_id}: {response.text}"
        )

    data = response.json()
    meeting_uri = data.get("meetingUri")
    if meeting_uri:
        return meeting_uri

    meeting_code = data.get("meetingCode")
    if meeting_code:
        return f"https://meet.google.com/{meeting_code}"

    raise RuntimeError("Google Meet spaces.create did not return meetingUri or meetingCode.")
