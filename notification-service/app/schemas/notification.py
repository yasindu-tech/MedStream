from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.models.notification import NotificationChannel, NotificationStatus

# Base Schema
class NotificationBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# Event Schemas
class EventCreate(NotificationBase):
    event_type: str
    user_id: UUID
    payload: Dict[str, Any]
    channels: Optional[List[NotificationChannel]] = None
    priority: str = "normal"  # "normal" | "critical"

class EventResponse(NotificationBase):
    notification_id: UUID
    status: str

# Preference Schemas
class PreferenceUpdate(NotificationBase):
    email_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None

class PreferenceRead(NotificationBase):
    user_id: UUID
    email_enabled: bool
    in_app_enabled: bool

# History Schemas
class HistoryRead(NotificationBase):
    id: UUID
    user_id: UUID
    event_type: str
    channel: NotificationChannel
    title: Optional[str]
    message: str
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime

class InboxResponse(NotificationBase):
    items: List[HistoryRead]
    total: int
    unread_count: int

# Template Schemas
class TemplateCreate(NotificationBase):
    name: str
    channel: NotificationChannel
    subject: Optional[str] = None
    body_template: str
    event_type: str
    is_active: bool = True

class TemplateUpdate(NotificationBase):
    name: Optional[str] = None
    channel: Optional[NotificationChannel] = None
    subject: Optional[str] = None
    body_template: Optional[str] = None
    event_type: Optional[str] = None
    is_active: Optional[bool] = None

class TemplateRead(NotificationBase):
    id: UUID
    name: str
    channel: NotificationChannel
    subject: Optional[str]
    body_template: str
    event_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

# Queue Schemas
class QueueStatusResponse(NotificationBase):
    id: UUID
    status: NotificationStatus
    retry_count: int
    processed_at: Optional[datetime]
    created_at: datetime
