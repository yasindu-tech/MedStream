from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, timedelta
from datetime import datetime
from uuid import UUID
import logging
from typing import Optional, Dict, Any, List

from app.models.notification import (
    NotificationTemplate, 
    UserNotificationPreference, 
    NotificationQueue, 
    NotificationHistory, 
    NotificationStatus
)
from app.services.email_service import EmailService
from app.services.template_service import TemplateService
from app.services.websocket_service import manager
from app.database import SessionLocal

logger = logging.getLogger(__name__)

async def process_notification_queue():
    """
    Background worker that processes the pending notification queue.
    Checks for items where scheduled_at <= now.
    """
    async with SessionLocal() as db:
        stmt = (
            select(NotificationQueue)
            .where(NotificationQueue.status.in_([NotificationStatus.QUEUED, NotificationStatus.FAILED]))
            .where(NotificationQueue.retry_count < NotificationQueue.max_retries)
            .where(NotificationQueue.scheduled_at <= datetime.utcnow())
            .limit(10)
        )
        result = await db.execute(stmt)
        items = result.scalars().all()

        for item in items:
            try:
                # 1. Get Template
                temp_stmt = select(NotificationTemplate).where(NotificationTemplate.event_type == item.event_type)
                temp_res = await db.execute(temp_stmt)
                template = temp_res.scalar_one_or_none()
                
                if not template:
                    item.status = NotificationStatus.FAILED
                    continue

                # 2. Render
                rendered_title = TemplateService.render_subject(template.title_template, item.payload)
                rendered_body = TemplateService.render_body(template.body_template, item.payload)

                # 3. Dispatch Email
                success = EmailService.send_email(
                    to_email=item.payload.get("email", "patient@medstream.lk"),
                    subject=rendered_title,
                    html_content=rendered_body
                )

                if success:
                    item.status = NotificationStatus.SENT
                    item.processed_at = datetime.utcnow()
                    
                    # Log to history
                    history = NotificationHistory(
                        user_id=item.user_id,
                        event_type=item.event_type,
                        channel=item.channel,
                        title=rendered_title,
                        message=rendered_body
                    )
                    db.add(history)
                else:
                    item.status = NotificationStatus.FAILED
                    item.retry_count += 1
                    
                    if item.retry_count >= item.max_retries:
                        # Alert Admin on permanent exhaustion
                        service = NotificationService(db)
                        await service.create_notification_from_event(
                            event_type="system.incident",
                            user_id=UUID("00000000-0000-0000-0000-000000000000"), # Admin ID
                            payload={"incident": f"Permanent failure for {item.event_type}", "queue_id": str(item.id)},
                            priority="critical"
                        )
                        logger.error(f"Notification {item.id} exhausted all retries and failed permanently.")
                    else:
                        # Exponential Backoff (5min, 15min...)
                        delay_minutes = 5 * (3 ** (item.retry_count - 1))
                        item.scheduled_at = datetime.utcnow() + timedelta(minutes=delay_minutes)
                        logger.warning(f"Notification {item.id} failed attempt {item.retry_count}. Retrying in {delay_minutes} minutes.")
                
            except Exception as e:
                logger.error(f"Error in background worker for item {item.id}: {e}")
                item.status = NotificationStatus.FAILED
                item.retry_count += 1

        await db.commit()

class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def handle_event(self, event_data: Any) -> Optional[UUID]:
        """
        Public entry point for intake (matches the router's expectations).
        """
        return await self.create_notification_from_event(
            event_type=event_data.event_type,
            user_id=event_data.user_id,
            payload=event_data.payload,
            priority=event_data.priority,
            scheduled_at=event_data.scheduled_at
        )

    async def create_notification_from_event(
        self, 
        event_type: str, 
        user_id: UUID, 
        payload: Dict[str, Any], 
        priority: str = "normal",
        scheduled_at: Optional[datetime] = None
    ) -> Optional[UUID]:
        
        # 1. Get Template
        stmt = select(NotificationTemplate).where(NotificationTemplate.event_type == event_type)
        result = await self.db.execute(stmt)
        template = result.scalar_one_or_none()
        
        if not template or not template.is_active:
            logger.warning(f"No active template for: {event_type}")
            return None

        # 2. De-duplication check (60s)
        sixty_seconds_ago = datetime.utcnow() - timedelta(seconds=60)
        dup_stmt = (
            select(NotificationHistory)
            .where(NotificationHistory.user_id == user_id)
            .where(NotificationHistory.event_type == event_type)
            .where(NotificationHistory.created_at >= sixty_seconds_ago)
        )
        dup_result = await self.db.execute(dup_stmt)
        if dup_result.scalar_one_or_none():
            logger.info(f"Skipping duplicate: {event_type}")
            return None

        # 3. Preferences & Critical Bypass
        pref_stmt = select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
        pref_res = await self.db.execute(pref_stmt)
        prefs = pref_res.scalar_one_or_none()
        
        is_mandatory = (priority == "critical")
        if is_mandatory:
            logger.info(f"AUDIT: Bypassing preferences for critical event: {event_type}")
        
        # 4. Render
        title = TemplateService.render_subject(template.title_template, payload)
        body = TemplateService.render_body(template.body_template, payload)

        # 5. Routing
        target_channels = []
        for chan in template.channels:
            if is_mandatory:
                target_channels.append(chan)
            elif prefs:
                if chan == "email" and prefs.email_enabled: target_channels.append(chan)
                elif chan == "in_app" and prefs.in_app_enabled: target_channels.append(chan)
                elif chan == "sms" and prefs.sms_enabled: target_channels.append(chan)
            else:
                target_channels.append(chan)

        if not target_channels:
            return None

        # 6. Dispatch
        related_id = payload.get("entity_id") or payload.get("appointment_id") or payload.get("prescription_id")
        related_type = payload.get("entity_type") or event_type.split(".")[0]

        queue_id = None
        if "email" in target_channels:
            q_item = NotificationQueue(
                user_id=user_id,
                event_type=event_type,
                channel="email",
                payload=payload,
                status=NotificationStatus.QUEUED,
                scheduled_at=scheduled_at or datetime.utcnow()
            )
            self.db.add(q_item)
            await self.db.flush()
            queue_id = q_item.id

        if "in_app" in target_channels:
            h_item = NotificationHistory(
                user_id=user_id,
                event_type=event_type,
                title=title,
                message=body,
                channel="in_app",
                is_read=False,
                related_entity_id=UUID(str(related_id)) if related_id else None,
                related_entity_type=related_type
            )
            self.db.add(h_item)
            
            # Real-time Push
            await manager.send_personal_message({
                "type": "NEW_NOTIFICATION",
                "title": title,
                "message": body,
                "event_type": event_type
            }, str(user_id))

        await self.db.commit()
        return queue_id or user_id

async def seed_default_templates():
    async with SessionLocal() as db:
        defaults = [
            {
                "event_type": "appointment.booked",
                "title_template": "Appointment Confirmed",
                "body_template": "Hello {patient_name}, your appointment with {doctor_name} is confirmed for {date} at {time}.",
                "channels": ["email", "in_app"]
            },
            {
                "event_type": "appointment.cancelled",
                "title_template": "Appointment Cancelled",
                "body_template": "Dear {patient_name}, your appointment on {date} has been cancelled.",
                "channels": ["email", "in_app"]
            },
            {
                "event_type": "appointment.rescheduled",
                "title_template": "Appointment Rescheduled",
                "body_template": "Hello {patient_name}, your appointment with {doctor_name} has been moved to {new_date} at {new_time} (Prev: {old_date}).",
                "channels": ["email", "in_app"]
            },
            {
                "event_type": "appointment.reminder",
                "title_template": "Upcoming Appointment Reminder",
                "body_template": "Don't forget! Your appointment with {doctor_name} is in {time_remaining}. Location: {location}.",
                "channels": ["email", "in_app"]
            },
            {
                "event_type": "prescription.new",
                "title_template": "New Prescription Available",
                "body_template": "Dr. {doctor_name} has issued a new prescription for you. Please check your patient portal.",
                "channels": ["in_app"]
            },
            {
                "event_type": "auth.verification",
                "title_template": "Verify Your MedStream Account",
                "body_template": "Welcome to MedStream! Please use this code to verify your account: {otp}. Or click here: {verification_link}",
                "channels": ["email"]
            },
            {
                "event_type": "auth.password_reset",
                "title_template": "Reset Your Password",
                "body_template": "We received a request to reset your password. Click here to set a new one: {reset_link}. If you didn't request this, please ignore this email.",
                "channels": ["email"]
            },
            {
                "event_type": "account.approved",
                "title_template": "Account Approved",
                "body_template": "Congratulations! Your account has been approved. You can now access all MedStream services.",
                "channels": ["email", "in_app"]
            },
            {
                "event_type": "account.suspended",
                "title_template": "Account Suspended",
                "body_template": "Your account has been temporarily suspended. Reason: {reason}. Please contact support for more information.",
                "channels": ["email", "in_app"]
            },
            {
                "event_type": "medical_record.update",
                "title_template": "Your Medical Record has been updated",
                "body_template": "An update has been made to your medical care history. Please log in to your patient portal to review the new information.",
                "channels": ["in_app"]
            },
            {
                "event_type": "system.incident",
                "title_template": "CRITICAL INCIDENT: Operation Failure",
                "body_template": "A critical system incident was detected. Type: {incident}. Source Queue: {queue_id}. Please investigate immediately.",
                "channels": ["email", "in_app"]
            },
            {
                "event_type": "clinic.staff_updated",
                "title_template": "Clinic Staff Change",
                "body_template": "Administrative Update: The staff roster for clinic '{clinic_name}' has been updated. Change: {change_details}.",
                "channels": ["email", "in_app"]
            },
            {
                "event_type": "clinic.doctor_assigned",
                "title_template": "Doctor Assignment Update",
                "body_template": "Dr. {doctor_name} has been successfully assigned to your clinic: {clinic_name}.",
                "channels": ["email", "in_app"]
            },
            {
                "event_type": "telemedicine.reminder",
                "title_template": "Your Telemedicine Call is Starting",
                "body_template": "Your virtual consultation with Dr. {doctor_name} is starting in 10 minutes. Click here to join: {meeting_link}",
                "channels": ["email", "in_app"]
            }
        ]
        
        for d in defaults:
            stmt = select(NotificationTemplate).where(NotificationTemplate.event_type == d["event_type"])
            result = await db.execute(stmt)
            if not result.scalar_one_or_none():
                db.add(NotificationTemplate(**d))
        
        await db.commit()
