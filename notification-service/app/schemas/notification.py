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
    scheduled_at: Optional[datetime] = None

class EventResponse(NotificationBase):
    notification_id: UUID
    status: str

# Preference Schemas
class PreferenceUpdate(NotificationBase):
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None

class PreferenceRead(NotificationBase):
    user_id: UUID
    email_enabled: bool
    sms_enabled: bool
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
class TemplateBase(NotificationBase):
    event_type: str
    title_template: str
    body_template: str
    channels: List[NotificationChannel] = ["email", "in_app"]
    is_active: bool = True

class TemplateCreate(TemplateBase):
    pass

class TemplateUpdate(NotificationBase):
    title_template: Optional[str] = None
    body_template: Optional[str] = None
    channels: Optional[List[NotificationChannel]] = None
    is_active: Optional[bool] = None

class TemplateRead(TemplateBase):
    id: UUID
    version: int
    created_at: datetime
    updated_at: datetime

# Queue Schemas
class QueueStatusResponse(NotificationBase):
    id: UUID
    status: NotificationStatus
    retry_count: int
    processed_at: Optional[datetime]
    created_at: datetime


class ContactUsRequest(NotificationBase):
    email: str = Field(min_length=5, max_length=254)
    phone: str = Field(min_length=7, max_length=30)
    message: str = Field(min_length=5, max_length=4000)


class ContactUsResponse(NotificationBase):
    status: str
    detail: str
