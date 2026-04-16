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
                    success = EmailService.send_email(
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
        
        # 3. Render
        title = TemplateService.render_subject(template.subject, event_data.payload)
        message = TemplateService.render_body(template.body, event_data.payload)

        # 4. Save to Unified Notifications Table
        notification = Notification(
            user_id=event_data.user_id,
            template_id=template.template_id,
            event_type=event_data.event_type,
            channel=template.channel,
            title=title,
            message=message,
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
    # Python seeding is now a fallback; SQL handles the initial boot.
    async with AsyncSessionLocal() as db:
        pass
