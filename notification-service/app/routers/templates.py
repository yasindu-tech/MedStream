from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.notification import NotificationTemplate
from app.middleware import get_current_user

router = APIRouter(prefix="/templates")

@router.get("/", response_model=List[dict])
async def list_templates(db: AsyncSession = Depends(get_db)):
    stmt = select(NotificationTemplate).where(NotificationTemplate.status == 'active')
    result = await db.execute(stmt)
    templates = result.scalars().all()
    return [
        {
            "template_id": t.template_id,
            "event_type": t.event_type,
            "channel": t.channel,
            "subject": t.subject,
            "body": t.body,
            "status": t.status
        } for t in templates
    ]

@router.post("/")
async def create_template(data: dict, db: AsyncSession = Depends(get_db)):
    template = NotificationTemplate(**data)
    db.add(template)
    await db.commit()
    return {"status": "success", "template_id": template.template_id}
