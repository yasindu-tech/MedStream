from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timedelta
from uuid import UUID
import logging
from typing import Optional, Dict, Any

from app.models.notification import NotificationTemplate, UserNotificationPreference, NotificationQueue, NotificationHistory
from app.services.email_service import EmailService
from app.services.template_service import TemplateService
from app.services.websocket_service import manager
from app.constants import PRIORITY_MAP

logger = logging.getLogger(__name__)

async def create_notification_from_event(db: AsyncSession, event_type: str, user_id: UUID, payload: Dict[str, Any], priority: str = "normal"):
    # 1. Get Template
    stmt = select(NotificationTemplate).where(NotificationTemplate.event_type == event_type)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        logger.warning(f"No template found for event: {event_type}")
        return None

    # 2. Check Preferences
    stmt = select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
    result = await db.execute(stmt)
    prefs = result.scalar_one_or_none()
    
    # 3. Render content
    rendered_title = template.title_template.format(**payload)
    rendered_body = template.body_template.format(**payload)

    # 4. Queue Notification
    queue_item = NotificationQueue(
        user_id=user_id,
        event_type=event_type,
        title=rendered_title,
        body=rendered_body,
        priority=priority,
        channels=template.channels
    )
    
    db.add(queue_item)
    await db.commit()
    await db.refresh(queue_item)
    
    # 5. Real-time push via WebSocket
    await manager.send_personal_message({
        "type": "NEW_NOTIFICATION",
        "title": rendered_title,
        "message": rendered_body,
        "event_type": event_type
    }, str(user_id))
    
    return queue_item

async def seed_default_templates(db: AsyncSession):
    # Standard health-related templates
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
            "event_type": "prescription.new",
            "title_template": "New Prescription Available",
            "body_template": "Dr. {doctor_name} has issued a new prescription for you. Please check your patient portal.",
            "channels": ["in_app"]
        }
    ]
    
    for d in defaults:
        stmt = select(NotificationTemplate).where(NotificationTemplate.event_type == d["event_type"])
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            db.add(NotificationTemplate(**d))
    
    await db.commit()
