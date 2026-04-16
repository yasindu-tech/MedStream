import httpx
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

class SMSService:
    API_URL = "https://app.text.lk/api/v3/sms/send"

    @staticmethod
    async def send_sms(recipient: str, message: str) -> bool:
        """
        Sends an SMS via Text.lk API.
        Acceptance Criteria:
        - Trim content to 160 characters
        - Track delivery attempt
        - Handle gateway outages
        """
        # Trim message for SMS constraints 
        trimmed_message = message[:160]
        
        if not settings.TEXT_LK_API_TOKEN:
            logger.info(f"[MOCK SMS] To: {recipient} | Msg: {trimmed_message}")
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
                response = await client.post(SMSService.API_URL, json=payload, headers=headers, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        logger.info(f"SMS sent successfully to {recipient}")
                        return True
                    else:
                        logger.error(f"Text.lk Error: {data.get('message')}")
                        return False
                else:
                    logger.error(f"SMS Gateway Error: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Failed to communicate with SMS Gateway: {str(e)}")
            return False
