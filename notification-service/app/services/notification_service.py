import logging
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notification import (
    NotificationTemplate, NotificationQueue, NotificationHistory, 
    UserNotificationPreference, NotificationChannel, NotificationStatus
)
from app.schemas.notification import EventCreate
from app.services.template_service import TemplateService
from app.services.email_service import EmailService
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def seed_default_templates():
    """Seed default templates on startup if they don't exist."""
    templates = [
        {
            "name": "appointment_booked_email",
            "channel": NotificationChannel.EMAIL,
            "event_type": "appointment.booked",
            "subject": "Appointment Confirmed",
            "body_template": "Dear {patient_name}, your appointment with Dr. {doctor_name} is confirmed for {date} at {time}. Appointment ID: {appointment_id}."
        },
        {
            "name": "appointment_booked_inapp",
            "channel": NotificationChannel.IN_APP,
            "event_type": "appointment.booked",
            "subject": "Appointment Confirmed",
            "body_template": "Your appointment with Dr. {doctor_name} on {date} at {time} has been confirmed."
        },
        {
            "name": "appointment_cancelled_inapp",
            "channel": NotificationChannel.IN_APP,
            "event_type": "appointment.cancelled",
            "subject": "Appointment Cancelled",
            "body_template": "Your appointment on {date} has been cancelled. Reason: {reason}."
        },
        {
            "name": "account_verification_email",
            "channel": NotificationChannel.EMAIL,
            "event_type": "account.verification",
            "subject": "Verify Your Account",
            "body_template": "Welcome to MedStream! Please verify your account using this code: {otp_code}. This code expires in {expiry_minutes} minutes."
        },
        {
            "name": "password_reset_email",
            "channel": NotificationChannel.EMAIL,
            "event_type": "account.password_reset",
            "subject": "Password Reset Request",
            "body_template": "A password reset was requested for your account. Use this code: {reset_code}. Expires in {expiry_minutes} minutes. Ignore if not requested."
        },
        {
            "name": "prescription_available_inapp",
            "channel": NotificationChannel.IN_APP,
            "event_type": "prescription.available",
            "subject": "New Prescription Available",
            "body_template": "Dr. {doctor_name} has issued a new prescription following your consultation on {consultation_date}. Please log in to review it."
        }
    ]

    async with AsyncSessionLocal() as db:
        for t_data in templates:
            stmt = select(NotificationTemplate).where(NotificationTemplate.name == t_data["name"])
            result = await db.execute(stmt)
            if not result.scalar_one_or_none():
                db.add(NotificationTemplate(**t_data))
        await db.commit()

class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def handle_event(self, event: EventCreate):
        """
        Main entry point for intake.
        1. Check for duplicates (last 60s).
        2. Get templates for event_type.
        3. Check preferences (unless critical).
        4. Queue notifications.
        5. Trigger processing.
        """
        # 1. Deduplication check
        payload_hash = hashlib.md5(json.dumps(event.payload, sort_keys=True).encode()).hexdigest()
        one_minute_ago = datetime.now(timezone.utc) - timedelta(seconds=60)
        
        dup_stmt = select(NotificationQueue).where(
            NotificationQueue.user_id == event.user_id,
            NotificationQueue.event_type == event.event_type,
            NotificationQueue.created_at >= one_minute_ago
        )
        # In a real app, I'd compare the payload hash too, but the prompt says 
        # "if a notification_queue entry with the same user_id + event_type + payload hash exists"
        # I'll stick to that.
        result = await self.db.execute(dup_stmt)
        existing = result.scalars().all()
        for entry in existing:
            if hashlib.md5(json.dumps(entry.payload, sort_keys=True).encode()).hexdigest() == payload_hash:
                logger.info(f"Duplicate event ignored for user {event.user_id}, type {event.event_type}")
                return None

        # 2. Get active templates
        temp_stmt = select(NotificationTemplate).where(
            NotificationTemplate.event_type == event.event_type,
            NotificationTemplate.is_active == True
        )
        result = await self.db.execute(temp_stmt)
        templates = result.scalars().all()

        if not templates:
            logger.warning(f"No active templates found for event type: {event.event_type}")
            return None

        # 3. Check preferences
        pref_stmt = select(UserNotificationPreference).where(UserNotificationPreference.user_id == event.user_id)
        result = await self.db.execute(pref_stmt)
        prefs = result.scalar_one_or_none()
        
        # Default preferences if none exist
        if not prefs:
            prefs = UserNotificationPreference(user_id=event.user_id, email_enabled=True, in_app_enabled=True)

        queued_ids = []
        for template in templates:
            # Skip if channel not requested and channels provided
            if event.channels and template.channel not in event.channels:
                continue
                
            # Skip if preference disabled (and not critical)
            if event.priority != "critical":
                if template.channel == NotificationChannel.EMAIL and not prefs.email_enabled:
                    continue
                if template.channel == NotificationChannel.IN_APP and not prefs.in_app_enabled:
                    continue
            
            # 4. Queue entry
            new_queue = NotificationQueue(
                user_id=event.user_id,
                event_type=event.event_type,
                channel=template.channel,
                template_id=template.id,
                payload=event.payload,
                status=NotificationStatus.QUEUED
            )
            self.db.add(new_queue)
            await self.db.flush() # Get the ID
            queued_ids.append(new_queue.id)
            
            # 5. Process immediately
            await self.process_notification(new_queue)

        await self.db.commit()
        return queued_ids[0] if queued_ids else None

    async def process_notification(self, queue_item: NotificationQueue):
        """Dispatches a single queued notification."""
        queue_item.status = NotificationStatus.PROCESSING
        await self.db.flush()

        temp_stmt = select(NotificationTemplate).where(NotificationTemplate.id == queue_item.template_id)
        result = await self.db.execute(temp_stmt)
        template = result.scalar_one_or_none()
        
        if not template:
            queue_item.status = NotificationStatus.FAILED
            logger.error(f"Template {queue_item.template_id} not found for queue {queue_item.id}")
            return

        title = TemplateService.render_subject(template.subject, queue_item.payload)
        body = TemplateService.render_body(template.body_template, queue_item.payload)

        success = False
        if queue_item.channel == NotificationChannel.EMAIL:
            # We need user email. If not in payload, we'd fetch it.
            email_addr = queue_item.payload.get("email") or await EmailService.get_user_email(str(queue_item.user_id))
            success = await EmailService.send_email(email_addr, title, body)
        elif queue_item.channel == NotificationChannel.IN_APP:
            success = True # In-app is just history insertion
        elif queue_item.channel == NotificationChannel.SMS:
            logger.warning("SMS channel not implemented. Skipping.")
            success = False

        if success:
            queue_item.status = NotificationStatus.SENT
            queue_item.processed_at = datetime.now(timezone.utc)
            
            # Insert into history
            history = NotificationHistory(
                queue_id=queue_item.id,
                user_id=queue_item.user_id,
                event_type=queue_item.event_type,
                channel=queue_item.channel,
                title=title,
                message=body,
                related_entity_type=queue_item.payload.get("entity_type"),
                related_entity_id=queue_item.payload.get("entity_id")
            )
            self.db.add(history)
        else:
            queue_item.retry_count += 1
            if queue_item.retry_count >= queue_item.max_retries:
                queue_item.status = NotificationStatus.FAILED
            else:
                queue_item.status = NotificationStatus.QUEUED
        
        await self.db.flush()
