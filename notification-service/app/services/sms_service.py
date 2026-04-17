import httpx
from typing import Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class SMSService:
    @staticmethod
    async def send_sms(recipient: str, message: str) -> bool:
        """
        Sends an SMS via Text.lk API.
        """
        trimmed_message = message[:160]
        
        if not settings.TEXT_LK_API_TOKEN:
            logger.error("TEXT_LK_API_TOKEN is missing; cannot send SMS.")
            return False

        headers = {
            "Authorization": f"Bearer {settings.TEXT_LK_API_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        payload = {
            "recipient": recipient,
            "sender_id": settings.TEXT_LK_SENDER_ID,
            "type": "plain",
            "message": trimmed_message
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(settings.TEXT_LK_API_URL, json=payload, headers=headers, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("status") == "success"
                logger.error("Text.lk returned non-200 response: %s %s", response.status_code, response.text)
                return False

        except Exception as exc:
            logger.error("SMS send failed: %s", exc)
            return False
