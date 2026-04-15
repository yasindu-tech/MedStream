import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    async def send_email(to_email: str, subject: str, body: str) -> bool:
        """
        Send an email using SMTP.
        If ENVIRONMENT=development, logs the email instead of sending.
        """
        if settings.ENVIRONMENT == "development":
            logger.info("--- MOCK EMAIL START ---")
            logger.info(f"To: {to_email}")
            logger.info(f"Subject: {subject}")
            logger.info(f"Body: {body}")
            logger.info("--- MOCK EMAIL END ---")
            return True

        try:
            msg = MIMEMultipart()
            msg['From'] = settings.EMAIL_FROM
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
        
    @staticmethod
    async def get_user_email(user_id: str) -> str:
        """
        Mock function to get user email. 
        In a real scenario, this would call auth-service or patient-service.
        For now, we'll assume a pattern or return a placeholder if not in payload.
        """
        # Note: The prompt doesn't specify how to get the email if not in payload.
        # Calling auth-service or assuming it's passed in payload.
        return f"user_{user_id}@example.com"
        
