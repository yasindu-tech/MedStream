from enum import Enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, Integer, JSON, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"

class NotificationStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"

class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    __table_args__ = {"schema": "communication"}

    template_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    event_type = Column(String(100), unique=True, nullable=False, index=True)
    channel = Column(String(50), nullable=False)
    subject = Column(String(255))
    body = Column(Text, nullable=False)
    status = Column(String(20), default='active')
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    notifications = relationship("Notification", back_populates="template")

class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = {"schema": "communication"}

    notification_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    
    @property
    def id(self):
        return self.notification_id

    user_id = Column(UUID(as_uuid=True), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("communication.notification_templates.template_id"))
    event_type = Column(String(100))
    channel = Column(String(50), nullable=False)
    title = Column(String(255))
    message = Column(Text, nullable=False)
    payload = Column(JSON)
    status = Column(String(20), default='queued') # queued, sent, failed, read
    sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    template = relationship("NotificationTemplate", back_populates="notifications")

# Aliases for backward compatibility or different architectural views
NotificationQueue = Notification
NotificationHistory = Notification

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = {"schema": "communication"}

    preference_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    email_enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=True)
    in_app_enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

# Alias for what __init__.py expects
UserNotificationPreference = NotificationPreference
