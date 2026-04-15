from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from app.database import get_db
from app.schemas.notification import InboxResponse, HistoryRead
from app.models.notification import NotificationHistory
from app.middleware import get_current_user
from datetime import datetime, timezone
from uuid import UUID
from typing import Dict

router = APIRouter()

@router.get("/inbox", response_model=InboxResponse)
async def get_inbox(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):
    offset = (page - 1) * limit
    user_id = UUID(current_user["user_id"])

    # Base query
    query = select(NotificationHistory).where(NotificationHistory.user_id == user_id)
    if unread_only:
        query = query.where(NotificationHistory.is_read == False)
    
    # Total count
    count_stmt = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Unread count
    unread_stmt = select(func.count()).where(
        NotificationHistory.user_id == user_id, 
        NotificationHistory.is_read == False
    )
    unread_result = await db.execute(unread_stmt)
    unread_count = unread_result.scalar() or 0

    # Paged items
    items_stmt = query.order_by(NotificationHistory.created_at.desc()).offset(offset).limit(limit)
    items_result = await db.execute(items_stmt)
    items = items_result.scalars().all()

    return {
        "items": items,
        "total": total,
        "unread_count": unread_count
    }

@router.patch("/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_as_read(
    notification_id: UUID, 
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):
    user_id = UUID(current_user["user_id"])
    stmt = update(NotificationHistory).where(
        NotificationHistory.id == notification_id,
        NotificationHistory.user_id == user_id,
        NotificationHistory.is_read == False
    ).values(is_read=True, read_at=datetime.now(timezone.utc)).returning(NotificationHistory.id)
    
    result = await db.execute(stmt)
    updated_id = result.scalar_one_or_none()
    
    if not updated_id:
        # Check if it exists at all
        check_stmt = select(NotificationHistory).where(
            NotificationHistory.id == notification_id,
            NotificationHistory.user_id == user_id
        )
        res = await db.execute(check_stmt)
        if not res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Notification not found")
        return {"message": "Already read"}
    
    await db.commit()
    return {"message": "Marked as read"}

@router.patch("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):
    user_id = UUID(current_user["user_id"])
    stmt = update(NotificationHistory).where(
        NotificationHistory.user_id == user_id,
        NotificationHistory.is_read == False
    ).values(is_read=True, read_at=datetime.now(timezone.utc)).returning(NotificationHistory.id)
    
    result = await db.execute(stmt)
    updated_count = len(result.scalars().all())
    
    await db.commit()
    return {"updated_count": updated_count}

@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):
    user_id = UUID(current_user["user_id"])
    stmt = select(func.count()).where(
        NotificationHistory.user_id == user_id, 
        NotificationHistory.is_read == False
    )
    result = await db.execute(stmt)
    count = result.scalar() or 0
    return {"count": count}
