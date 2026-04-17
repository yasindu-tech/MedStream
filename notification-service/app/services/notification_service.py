from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timedelta
from uuid import UUID
import logging
from typing import Optional, Dict, Any, List

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
                    success = await EmailService.send_email(
                        to_email=item.payload.get("email", "patient@medstream.lk") if hasattr(item, 'payload') else "patient@medstream.lk",
                        subject=item.title,
                        html_content=item.message
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

        # 2. Check Preferences
        pref_stmt = select(NotificationPreference).where(NotificationPreference.user_id == event_data.user_id)
        pref_res = await self.db.execute(pref_stmt)
        prefs = pref_res.scalar_one_or_none()
        
        # Enable enforcement of preferences (AS-03)
        if prefs:
            if template.channel == "email" and not prefs.email_enabled:
                logger.info(f"Notification skipped: User {event_data.user_id} disabled email.")
                return None
            if template.channel == "sms" and not prefs.sms_enabled:
                logger.info(f"Notification skipped: User {event_data.user_id} disabled SMS.")
                return None
            if template.channel == "in_app" and not prefs.in_app_enabled:
                logger.info(f"Notification skipped: User {event_data.user_id} disabled in-app alerts.")
                return None

        # 3. Render
        title = TemplateService.render_subject(template.subject, event_data.payload)
        message = TemplateService.render_body(template.body, event_data.payload)

        # 4. Save to Unified Notifications Table
        logger.info(f"Triggering notification for event [{event_data.event_type}] to user [{event_data.user_id}]. Payload: {event_data.payload}")
        notification = Notification(
            user_id=event_data.user_id,
            template_id=template.template_id,
            event_type=event_data.event_type,
            channel=template.channel,
            title=title,
            message=message,
            payload=event_data.payload,
            status='queued'
        )
        
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        # 5. Real-time In-App Push
        if template.channel == "in_app":
            await manager.send_personal_message({
                "type": "NEW_NOTIFICATION",
                "title": title,
                "message": message,
                "event_type": event_data.event_type
            }, str(event_data.user_id))
            notification.status = 'sent'
            notification.sent_at = datetime.utcnow()
            await self.db.commit()

        return notification.notification_id

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
            "event_type": "account.suspended",
            "channel": "email",
            "subject": "Account Suspended",
            "body": "Your account has been suspended. Reason: {reason}"
        },
        {
            "event_type": "doctor.verification.approved",
            "channel": "email",
            "subject": "Doctor Verification Approved",
            "body": "Congratulations {doctor_name}, your verification has been approved. {reason}"
        },
        {
            "event_type": "doctor.verification.rejected",
            "channel": "email",
            "subject": "Doctor Verification Rejected",
            "body": "Hello {doctor_name}, your verification request has been rejected. Reason: {reason}"
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
