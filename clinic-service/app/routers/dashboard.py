from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import ClinicDashboardResponse, PlatformDashboardResponse
from app.services.clinic import get_clinic_by_id, get_clinic_admin_clinic_id
from app.services.dashboard import build_clinic_dashboard, build_platform_summary

router = APIRouter(tags=["Dashboard"])


def _ensure_clinic_admin_scope(db: Session, user: dict, clinic_id: str) -> None:
    if user["role"] != "clinic_admin":
        return

    assigned_clinic_id = get_clinic_admin_clinic_id(db, user["sub"])
    if not assigned_clinic_id or str(assigned_clinic_id) != str(clinic_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clinic admin is not permitted to view this clinic dashboard.",
        )


@router.get("/clinics/{clinic_id}/dashboard", response_model=ClinicDashboardResponse)
def clinic_dashboard(
    clinic_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("clinic_admin", "admin")),
) -> ClinicDashboardResponse:
    clinic = get_clinic_by_id(db, str(clinic_id))
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found.")

    _ensure_clinic_admin_scope(db, _user, str(clinic_id))
    return build_clinic_dashboard(db=db, clinic_id=str(clinic_id))


@router.get("/platform/summary", response_model=PlatformDashboardResponse)
def platform_summary(
    target_date: date | None = Query(
        None,
        description="Date used for daily booking counts. Defaults to today if not provided.",
    ),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("admin")),
) -> PlatformDashboardResponse:
    return build_platform_summary(db=db, target_date=target_date)
