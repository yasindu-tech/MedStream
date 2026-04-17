import httpx
import logging
from datetime import datetime, timezone
from app.config import settings

logger = logging.getLogger(__name__)

async def send_notification(event_type: str, user_id: str, payload: dict, priority: str = "normal"):
    """
    Sends a notification event to the notification-service.
    Fire-and-forget: failure must never cause the payment transaction to roll back.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{settings.NOTIFICATION_SERVICE_URL.rstrip('/')}/api/notifications/events",
                json={
                    "event_type": event_type,
                    "user_id": user_id,
                    "payload": payload,
                    "priority": priority
                }
            )
            if response.status_code >= 400:
                logger.warning(f"Notification service returned error {response.status_code}: {response.text}")
    except Exception as e:
        logger.warning(f"Notification failed: {e}")
