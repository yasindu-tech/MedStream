from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.notification import Notification
from app.middleware import get_current_user

router = APIRouter(prefix="/inbox")

@router.get("/", response_model=List[dict])
async def get_notification_history(
    skip: int = 0, 
    limit: int = 20, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    user_id = UUID(current_user["user_id"])
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .where(Notification.channel == "in_app")
        .order_by(Notification.created_at.desc())
        .offset(skip).limit(limit)
    )
    result = await db.execute(stmt)
    notifications = result.scalars().all()
    
    # Map to expected output for frontend
    return [
        {
            "id": n.notification_id,
            "title": n.title,
            "message": n.message,
            "status": n.status,
            "created_at": n.created_at
        } for n in notifications
    ]

@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    user_id = UUID(current_user["user_id"])
    stmt = (
        select(func.count(Notification.notification_id))
        .where(Notification.user_id == user_id)
        .where(Notification.status == 'queued') # Assuming 'queued' means unread for in-app
    )
    result = await db.execute(stmt)
    return {"unread_count": result.scalar()}
