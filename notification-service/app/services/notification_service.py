from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from uuid import UUID
import logging
from typing import Optional, Dict, Any, List
import httpx

from app.models.notification import (
    NotificationTemplate, 
    NotificationPreference, 
    Notification
)
from app.services.email_service import EmailService
from app.services.sms_service import SMSService
from app.services.template_service import TemplateService
from app.services.websocket_service import manager
from app.database import AsyncSessionLocal
from app.config import settings

logger = logging.getLogger(__name__)

async def process_notification_queue():
    """
    Background worker that processes the pending 'notifications' table.
    Checks for items where status='queued' and scheduled time has arrived.
    """
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Notification)
            .where(Notification.status.in_(['queued', 'failed']))
            .limit(10)
        )
        result = await db.execute(stmt)
        items = result.scalars().all()

        for item in items:
            try:
                # 3. Dispatch Layer (Route by channel)
                success = False
                if item.channel == "email":
                    email_payload = item.payload if isinstance(item.payload, dict) else {}
                    success = await EmailService.send_email(
                        to_email=email_payload.get("email", "patient@medstream.lk"),
                        subject=item.title,
                        html_content=_build_email_html(
                            title=item.title,
                            message=item.message,
                            payload=email_payload,
                            event_type=item.event_type,
                        )
                    )
                elif item.channel == "sms":
                    # Get phone from payload - no fallback
                    phone = item.payload.get("phone") if hasattr(item, 'payload') else None
                    if not phone:
                        logger.error(f"Cannot send SMS for notification {item.notification_id}: Missing recipient phone number.")
                        success = False
                    else:
                        success = await SMSService.send_sms(
                            recipient=phone,
                            message=item.message
                        )

                if success:
                    item.status = 'sent'
                    item.sent_at = datetime.utcnow()
                else:
                    item.status = 'failed'
                
            except Exception as e:
                logger.error(f"Error in background worker for item {item.notification_id}: {e}")
                item.status = 'failed'

        await db.commit()

class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def handle_event(self, event_data: Any) -> Optional[UUID]:
        # 1. Get Template
        stmt = select(NotificationTemplate).where(NotificationTemplate.event_type == event_data.event_type)
        result = await self.db.execute(stmt)
        template = result.scalar_one_or_none()
        
        if not template or template.status != 'active':
            return None

        # 2. Check Preferences (fail-open if preference schema is out of sync)
        prefs = None
        try:
            pref_stmt = select(NotificationPreference).where(NotificationPreference.user_id == event_data.user_id)
            pref_res = await self.db.execute(pref_stmt)
            prefs = pref_res.scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.warning(
                "Notification preferences unavailable for user %s, continuing with defaults: %s",
                event_data.user_id,
                exc,
            )
        
        # 3. Render
        contact = _resolve_user_contact(str(event_data.user_id))
        if isinstance(event_data.payload, dict):
            if contact.get("email") and not event_data.payload.get("email"):
                event_data.payload["email"] = contact["email"]
            if contact.get("phone") and not event_data.payload.get("phone"):
                event_data.payload["phone"] = contact["phone"]

        title = TemplateService.render_subject(template.subject, event_data.payload)
        message = TemplateService.render_body(template.body, event_data.payload)

        requested_channels = event_data.channels or [template.channel]
        channels_to_send = [
            channel for channel in requested_channels
            if _is_channel_enabled(channel, prefs)
        ]

        if not channels_to_send:
            return None

        # 4. Save one notification row per requested channel.
        logger.info(
            "Triggering notification event [%s] to user [%s] via channels %s. Payload: %s",
            event_data.event_type,
            event_data.user_id,
            channels_to_send,
            event_data.payload,
        )

        notifications: list[Notification] = []
        for channel in channels_to_send:
            notification = Notification(
                user_id=event_data.user_id,
                template_id=template.template_id,
                event_type=event_data.event_type,
                channel=channel,
                title=title,
                message=message,
                payload=event_data.payload,
                status='queued'
            )
            self.db.add(notification)
            notifications.append(notification)

        await self.db.commit()
        for notification in notifications:
            await self.db.refresh(notification)

        # 5. Real-time In-App Push for in_app channel.
        for notification in notifications:
            if notification.channel == "in_app":
                await manager.send_personal_message({
                    "type": "NEW_NOTIFICATION",
                    "title": title,
                    "message": message,
                    "event_type": event_data.event_type
                }, str(event_data.user_id))
                notification.status = 'sent'
                notification.sent_at = datetime.utcnow()

        await self.db.commit()
        return notifications[0].notification_id


def _is_channel_enabled(channel: str, prefs: NotificationPreference | None) -> bool:
    if not prefs:
        return True

    if channel == "email":
        return bool(getattr(prefs, "email_enabled", True))
    if channel == "sms":
        return bool(getattr(prefs, "sms_enabled", True))
    if channel == "in_app":
        return bool(getattr(prefs, "in_app_enabled", True))
    return True


def _resolve_user_contact(user_id: str) -> dict[str, Optional[str]]:
    url = f"{settings.AUTH_SERVICE_URL}/internal/users/{user_id}"
    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
            return {
                "email": payload.get("email"),
                "phone": payload.get("phone"),
            }
    except Exception:
        return {
            "email": None,
            "phone": None,
        }


def _build_email_html(*, title: str | None, message: str, payload: dict[str, Any], event_type: str | None) -> str:
        body = (message or "").strip()
        if "<html" in body.lower():
                return body

        event_type_text = (event_type or "notification").replace(".", " ").title()
        friendly_title = (title or event_type_text or "Notification").strip()
        patient_name = payload.get("patient_name") or payload.get("name") or "Patient"

        detail_fields = [
                ("Appointment ID", payload.get("appointment_id")),
                ("Doctor", payload.get("doctor_name")),
                ("Clinic", payload.get("clinic_name")),
                ("Date", payload.get("date")),
                ("Time", payload.get("time") or payload.get("start_time")),
                ("Amount", _format_amount(payload)),
                ("Transaction Ref", payload.get("transaction_reference")),
                ("Status", payload.get("status")),
        ]

        detail_rows = "".join(
                f"<tr><td style='padding:8px 10px;color:#637381;font-size:13px;font-weight:600;width:160px;'>{label}</td>"
                f"<td style='padding:8px 10px;color:#111827;font-size:14px;'>{value}</td></tr>"
                for label, value in detail_fields
                if value not in (None, "")
        )

        details_block = ""
        if detail_rows:
                details_block = (
                        "<div style='margin-top:18px;border:1px solid #E5E7EB;border-radius:12px;overflow:hidden;'>"
                        "<table role='presentation' cellpadding='0' cellspacing='0' width='100%' style='border-collapse:collapse;background:#F9FAFB;'>"
                        f"{detail_rows}"
                        "</table></div>"
                )

        return f"""
<html>
    <body style="margin:0;padding:0;background:#F3F4F6;font-family:Arial,Helvetica,sans-serif;">
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="padding:28px 12px;">
            <tr>
                <td align="center">
                    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:640px;background:#ffffff;border-radius:16px;border:1px solid #E5E7EB;overflow:hidden;">
                        <tr>
                            <td style="padding:22px 24px;background:linear-gradient(135deg,#0B4F6C,#01BAEF);color:#ffffff;">
                                <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;opacity:.9;">MedStream</div>
                                <div style="font-size:24px;line-height:1.25;font-weight:700;margin-top:6px;">{friendly_title}</div>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:24px;">
                                <p style="margin:0 0 10px 0;color:#111827;font-size:15px;line-height:1.6;">Hello {patient_name},</p>
                                <p style="margin:0;color:#374151;font-size:15px;line-height:1.6;">{body}</p>
                                {details_block}
                                <p style="margin:18px 0 0 0;color:#6B7280;font-size:12px;line-height:1.6;">This is an automated MedStream {event_type_text.lower()} email. If anything looks incorrect, please contact support.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
</html>
""".strip()


def _format_amount(payload: dict[str, Any]) -> str | None:
        amount = payload.get("amount")
        currency = payload.get("currency")
        if amount in (None, ""):
                return None
        if currency:
                return f"{amount} {currency}"
        return str(amount)

async def seed_default_templates():
    """
    Seeds the database with default notification templates if they don't exist.
    """
    templates = [
        {
            "event_type": "appointment.booked",
            "channel": "email",
            "subject": "Appointment Confirmed",
            "body": "Hello {patient_name}, your appointment with {doctor_name} is confirmed for {date} at {time}."
        },
        {
            "event_type": "appointment.cancelled",
            "channel": "email",
            "subject": "Appointment Cancelled",
            "body": "Dear {patient_name}, your appointment with {doctor_name} on {date} has been cancelled."
        },
        {
            "event_type": "appointment.rescheduled",
            "channel": "email",
            "subject": "Appointment Rescheduled",
            "body": "Hello {patient_name}, your appointment with {doctor_name} has been rescheduled to {date} at {time}."
        },
        {
            "event_type": "account.verification",
            "channel": "email",
            "subject": "Verify Your Account",
            "body": "Your verification code is: {otp}"
        },
        {
            "event_type": "account.password_reset",
            "channel": "email",
            "subject": "Reset Your Password",
            "body": "Click here to reset your password: {reset_link}"
        },
        {
            "event_type": "prescription.available",
            "channel": "in_app",
            "subject": "New Prescription Available",
            "body": "Dr. {doctor_name} has issued a new prescription for you. You can view it in the app."
        },
        {
            "event_type": "payment.confirmed",
            "channel": "email",
            "subject": "Payment Received",
            "body": "Hello, your payment of {amount} {currency} for appointment {appointment_id} was successful. Transaction: {transaction_reference}"
        },
        {
            "event_type": "payment.failed",
            "channel": "email",
            "subject": "Payment Failed",
            "body": "Your payment of {amount} {currency} failed. Reason: {reason}. You have {retries_remaining} retries left."
        },
        {
            "event_type": "payment.refunded",
            "channel": "email",
            "subject": "Refund Processed",
            "body": "A refund of {refund_amount} {currency} has been processed for your payment. Reason: {reason}"
        }
    ]

    async with AsyncSessionLocal() as db:
        for t_data in templates:
            # Check if exists
            stmt = select(NotificationTemplate).where(NotificationTemplate.event_type == t_data["event_type"])
            result = await db.execute(stmt)
            if not result.scalar_one_or_none():
                db.add(NotificationTemplate(**t_data))
        
        await db.commit()
        logger.info("Default notification templates seeded successfully.")
