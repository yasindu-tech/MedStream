from __future__ import annotations

import os
from typing import Any

import httpx


NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8000")


def send_in_app_notification(event_type: str, user_id: str, payload: dict[str, Any], priority: str = "normal") -> None:
    body = {
        "event_type": event_type,
        "user_id": user_id,
        "payload": payload,
        "channels": ["in_app"],
        "priority": priority,
    }

    try:
        with httpx.Client(timeout=2.0) as client:
            client.post(f"{NOTIFICATION_SERVICE_URL.rstrip('/')}/api/notifications/events", json=body)
    except httpx.RequestError:
        # Fail-open: profile and medical updates should not fail if notification service is unavailable.
        return
