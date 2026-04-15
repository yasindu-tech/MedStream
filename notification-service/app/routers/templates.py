from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.database import get_db
from app.schemas.notification import TemplateRead, TemplateCreate, TemplateUpdate
from app.models.notification import NotificationTemplate
from app.middleware import require_roles
from uuid import UUID
from typing import List, Dict

router = APIRouter()

@router.get("/templates", response_model=List[TemplateRead])
async def get_templates(
    db: AsyncSession = Depends(get_db),
    admin: Dict = Depends(require_roles("admin"))
):
    stmt = select(NotificationTemplate)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/templates", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(
    template: TemplateCreate, 
    db: AsyncSession = Depends(get_db),
    admin: Dict = Depends(require_roles("admin"))
):
    db_template = NotificationTemplate(**template.model_dump())
    db.add(db_template)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    
    await db.refresh(db_template)
    return db_template

@router.patch("/templates/{template_id}", response_model=TemplateRead)
async def update_template(
    template_id: UUID,
    template_data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    admin: Dict = Depends(require_roles("admin"))
):
    stmt = select(NotificationTemplate).where(NotificationTemplate.id == template_id)
    result = await db.execute(stmt)
    db_template = result.scalar_one_or_none()
    
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    for key, value in template_data.model_dump(exclude_unset=True).items():
        setattr(db_template, key, value)
        
    await db.commit()
    await db.refresh(db_template)
    return db_template

@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID, 
    db: AsyncSession = Depends(get_db),
    admin: Dict = Depends(require_roles("admin"))
):
    # Soft delete as per priority 4.4
    stmt = update(NotificationTemplate).where(NotificationTemplate.id == template_id).values(is_active=False)
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Template not found")
        
    await db.commit()
    return None
