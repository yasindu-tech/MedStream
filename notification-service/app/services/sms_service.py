import httpx
from typing import Optional
from app.config import settings

class SMSService:
    @staticmethod
    async def send_sms(recipient: str, message: str) -> bool:
        """
        Sends an SMS via Text.lk API.
        """
        trimmed_message = message[:160]
        
        if not settings.TEXT_LK_API_TOKEN:
            return True

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
                return False

        except Exception:
            return False
