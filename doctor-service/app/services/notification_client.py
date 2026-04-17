import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def send_notification_event(event_type: str, user_id: str, payload: dict, channels: list[str] | None = None) -> None:
    url = f"{settings.NOTIFICATION_SERVICE_URL.rstrip('/')}/api/notifications/events"
    body = {
        "event_type": event_type,
        "user_id": user_id,
        "payload": payload,
        "channels": channels or ["email", "in_app"],
        "priority": "normal",
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(url, json=body)
            if response.status_code >= 300:
                logger.warning(
                    "Notification event '%s' failed for user %s: %s",
                    event_type,
                    user_id,
                    response.text,
                )
    except Exception as exc:
        logger.warning(
            "Notification event '%s' could not be sent for user %s: %s",
            event_type,
            user_id,
            str(exc),
        )
