import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base
import enum

class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"

class NotificationStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"
    EXPIRED = "expired"

# Mapping to existing DB types
channel_type = SQLEnum(
    NotificationChannel, 
    name="notification_channel", 
    schema="communication", 
    create_type=False
)
status_type = SQLEnum(
    NotificationStatus, 
    name="notification_status", 
    schema="communication", 
    create_type=False
)

class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    __table_args__ = {"schema": "communication"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    channel = Column(channel_type, nullable=False)
    subject = Column(String(255))
    body_template = Column(Text, nullable=False)
    event_type = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class UserNotificationPreference(Base):
    __tablename__ = "user_notification_preferences"
    __table_args__ = {"schema": "communication"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    email_enabled = Column(Boolean, default=True)
    in_app_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class NotificationQueue(Base):
    __tablename__ = "notification_queue"
    __table_args__ = {"schema": "communication"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    event_type = Column(String(100), nullable=False)
    channel = Column(channel_type, nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("communication.notification_templates.id"))
    payload = Column(JSONB, nullable=False, default={})
    status = Column(status_type, default=NotificationStatus.QUEUED)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    scheduled_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class NotificationHistory(Base):
    __tablename__ = "notification_history"
    __table_args__ = {"schema": "communication"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    queue_id = Column(UUID(as_uuid=True), ForeignKey("communication.notification_queue.id"))
    user_id = Column(UUID(as_uuid=True), nullable=False)
    event_type = Column(String(100), nullable=False)
    channel = Column(channel_type, nullable=False)
    title = Column(String(255))
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True))
    related_entity_type = Column(String(100))
    related_entity_id = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
