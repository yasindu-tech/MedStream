"""Internal clinic-service endpoints for service-to-service scope checks."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClinicAdmin, ClinicStaff

router = APIRouter(tags=["internal"])


@router.get("/staff/{user_id}/clinic")
def get_staff_clinic(user_id: UUID, db: Session = Depends(get_db)) -> dict:
    staff = (
        db.query(ClinicStaff)
        .filter(ClinicStaff.user_id == user_id, ClinicStaff.status == "active")
        .first()
    )
    if staff:
        return {"clinic_id": str(staff.clinic_id), "source": "clinic_staff"}

    admin = (
        db.query(ClinicAdmin)
        .filter(ClinicAdmin.user_id == user_id, ClinicAdmin.status == "active")
        .first()
    )
    if admin:
        return {"clinic_id": str(admin.clinic_id), "source": "clinic_admins"}

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active clinic assignment for user")
