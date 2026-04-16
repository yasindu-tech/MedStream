import smtplib
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    async def send_email(to_email: str, subject: str, html_content: str, text_content: Optional[str] = None):
        """
        Sends an email using the configured SMTP settings.
        Supports both HTML and Plain Text fallback.
        """
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            logger.info(f"[MOCK EMAIL] To: {to_email} | Subject: {subject} | Content: [REDACTED FOR SECURITY]")
            return True

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = to_email

        # Add plain text fallback if provided
        if text_content:
            msg.attach(MIMEText(text_content, "plain"))
        else:
            # Basic strip of HTML tags for plain text fallback
            msg.attach(MIMEText("Please view this email in an HTML-compatible client.", "plain"))

        msg.attach(MIMEText(html_content, "html"))

        def _send():
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_PASSWORD:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
                logger.info(f"Email sent successfully to {to_email}")
                return True

        try:
            return await asyncio.to_thread(_send)
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
