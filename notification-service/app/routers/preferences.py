from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database import get_db
from app.schemas.notification import PreferenceRead, PreferenceUpdate
from app.models.notification import UserNotificationPreference
from app.middleware import get_current_user
from uuid import UUID
from typing import Dict

router = APIRouter()

@router.get("/preferences", response_model=PreferenceRead)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):
    user_id = UUID(current_user["user_id"])
    stmt = select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
    result = await db.execute(stmt)
    prefs = result.scalar_one_or_none()
    
    if not prefs:
        # Return defaults if no record exists
        return {
            "user_id": user_id,
            "email_enabled": True,
            "in_app_enabled": True
        }
        
    return prefs

@router.put("/preferences", response_model=PreferenceRead)
async def update_preferences(
    pref_data: PreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):
    user_id = UUID(current_user["user_id"])
    stmt = select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
    result = await db.execute(stmt)
    prefs = result.scalar_one_or_none()
    
    if prefs:
        for key, value in pref_data.model_dump(exclude_unset=True).items():
            setattr(prefs, key, value)
    else:
        # Upsert: create if not exists
        prefs = UserNotificationPreference(
            user_id=user_id,
            email_enabled=pref_data.email_enabled if pref_data.email_enabled is not None else True,
            in_app_enabled=pref_data.in_app_enabled if pref_data.in_app_enabled is not None else True
        )
        db.add(prefs)
        
    await db.commit()
    await db.refresh(prefs)
    return prefs
