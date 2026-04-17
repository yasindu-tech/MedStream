from typing import List, Sequence

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import (
    ClinicActionResponse,
    ClinicResponse,
    CreateClinicRequest,
    UpdateClinicStatusRequest,
)
from app.services.clinic import (
    change_clinic_status,
    create_clinic,
    list_clinics,
    remove_clinic,
)

router = APIRouter(tags=["Clinics"])


@router.post("/", response_model=ClinicResponse, status_code=status.HTTP_201_CREATED)
def create_clinic_endpoint(
    payload: CreateClinicRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("admin")),
) -> ClinicResponse:
    clinic = create_clinic(db=db, payload=payload, created_by=_user["sub"])
    return ClinicResponse.model_validate(clinic)


@router.get("/", response_model=List[ClinicResponse])
def get_clinics_endpoint(
    active_only: bool = Query(False, description="If true, only active clinics are returned"),
    db: Session = Depends(get_db),
) -> Sequence[ClinicResponse]:
    return [ClinicResponse.model_validate(clinic) for clinic in list_clinics(db=db, active_only=active_only)]


@router.patch("/{clinic_id}/status", response_model=ClinicResponse)
def update_clinic_status_endpoint(
    clinic_id: str,
    payload: UpdateClinicStatusRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("admin")),
) -> ClinicResponse:
    clinic = change_clinic_status(
        db=db,
        clinic_id=clinic_id,
        new_status=payload.status,
        changed_by=_user["sub"],
        reason=payload.reason,
    )
    return ClinicResponse.model_validate(clinic)


@router.delete("/{clinic_id}", response_model=ClinicActionResponse)
def remove_clinic_endpoint(
    clinic_id: str,
    reason: str | None = Query(None, description="Optional reason for clinic removal"),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("admin")),
) -> ClinicActionResponse:
    clinic = remove_clinic(
        db=db,
        clinic_id=clinic_id,
        changed_by=_user["sub"],
        reason=reason,
    )
    return ClinicActionResponse(
        clinic_id=clinic.clinic_id,
        status=clinic.status,
        message="Clinic removed successfully.",
    )
