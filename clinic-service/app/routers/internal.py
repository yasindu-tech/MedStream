"""Internal clinic-service endpoints for service-to-service scope checks."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Clinic, ClinicAdmin, ClinicStaff

router = APIRouter(tags=["internal"])


@router.get("/staff/{user_id}/clinic")
def get_staff_clinic(user_id: UUID, db: Session = Depends(get_db)) -> dict:
    staff = (
        db.query(ClinicStaff)
        .join(Clinic, Clinic.clinic_id == ClinicStaff.clinic_id)
        .filter(
            ClinicStaff.user_id == user_id,
            ClinicStaff.status == "active",
            Clinic.status == "active",
        )
        .first()
    )
    if staff:
        return {"clinic_id": str(staff.clinic_id), "source": "clinic_staff"}

    admin = (
        db.query(ClinicAdmin)
        .join(Clinic, Clinic.clinic_id == ClinicAdmin.clinic_id)
        .filter(
            ClinicAdmin.user_id == user_id,
            ClinicAdmin.status == "active",
            Clinic.status == "active",
        )
        .first()
    )
    if admin:
        return {"clinic_id": str(admin.clinic_id), "source": "clinic_admins"}

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active clinic assignment for user")


@router.get("/clinics/{clinic_id}/status")
def get_clinic_status(clinic_id: UUID, db: Session = Depends(get_db)) -> dict:
    clinic = db.query(Clinic).filter(Clinic.clinic_id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found")
    return {
        "clinic_id": str(clinic.clinic_id),
        "status": clinic.status,
        "is_active": clinic.status == "active",
    }
