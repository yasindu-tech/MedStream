from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import UUID

from app.database import get_db
from app.models.notification import NotificationPreference
from app.middleware import get_current_user

router = APIRouter(prefix="/preferences")

@router.get("/")
async def get_my_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    user_id = UUID(current_user["user_id"])
    stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    result = await db.execute(stmt)
    prefs = result.scalar_one_or_none()
    
    if not prefs:
        # Return defaults if not set
        return {"email_enabled": True, "sms_enabled": True, "in_app_enabled": True}
    
    return prefs

@router.post("/")
async def update_preferences(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    user_id = UUID(current_user["user_id"])
    stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    result = await db.execute(stmt)
    prefs = result.scalar_one_or_none()
    
    if not prefs:
        prefs = NotificationPreference(user_id=user_id, **data)
        db.add(prefs)
    else:
        for key, value in data.items():
            setattr(prefs, key, value)
            
    await db.commit()
    return {"status": "success"}
