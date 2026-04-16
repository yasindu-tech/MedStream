from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.database import get_db
from app.models.notification import NotificationHistory
from app.middleware import get_current_user
from uuid import UUID
from typing import Dict, List, Optional
from datetime import datetime

router = APIRouter()

@router.get("/inbox")
async def get_user_inbox(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):
    """Retrieves paginated past notifications for the logged-in user."""
    user_id = UUID(current_user["user_id"])
    stmt = (
        select(NotificationHistory)
        .where(NotificationHistory.user_id == user_id)
        .order_by(NotificationHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    notifications = result.scalars().all()
    
    return notifications

@router.get("/inbox/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):
    """Returns the total number of unread notifications."""
    user_id = UUID(current_user["user_id"])
    stmt = (
        select(func.count(NotificationHistory.id))
        .where(NotificationHistory.user_id == user_id)
        .where(NotificationHistory.is_read == False)
    )
    result = await db.execute(stmt)
    count = result.scalar()
    
    return {"unread_count": count}

@router.post("/inbox/read-all")
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):
    """Marks all notifications for the current user as read."""
    user_id = UUID(current_user["user_id"])
    stmt = (
        update(NotificationHistory)
        .where(NotificationHistory.user_id == user_id)
        .where(NotificationHistory.is_read == False)
        .values(is_read=True, read_at=datetime.utcnow())
    )
    await db.execute(stmt)
    await db.commit()
    
    return {"status": "success", "message": "All notifications marked as read"}

@router.patch("/inbox/{notification_id}/read")
async def mark_single_as_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):
    """Marks a specific notification as read."""
    user_id = UUID(current_user["user_id"])
    stmt = (
        update(NotificationHistory)
        .where(NotificationHistory.id == notification_id)
        .where(NotificationHistory.user_id == user_id)
        .values(is_read=True, read_at=datetime.utcnow())
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    await db.commit()
    return {"status": "success"}
