from datetime import date
from typing import List, Optional, Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import (
    ClinicActionResponse,
    ClinicAppointmentListPaginatedResponse,
    ClinicResponse,
    ClinicUpdateRequest,
    CreateClinicRequest,
    UpdateClinicRequest,
    UpdateClinicStatusRequest,
)
from app.services.appointment_client import get_clinic_appointments
from app.services.clinic import (
    change_clinic_status,
    create_clinic,
    get_clinic_admin_clinic_id,
    get_clinic_by_id,
    list_clinics,
    remove_clinic,
    update_clinic,
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


@router.patch("/{clinic_id}", response_model=ClinicResponse)
def update_clinic_endpoint(
    clinic_id: str,
    payload: ClinicUpdateRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("admin")),
) -> ClinicResponse:
    clinic = update_clinic(
        db=db,
        clinic_id=clinic_id,
        payload=payload,
        changed_by=_user["sub"],
    )
    return ClinicResponse.model_validate(clinic)


@router.get("/{clinic_id}/appointments", response_model=ClinicAppointmentListPaginatedResponse)
def get_clinic_appointments_endpoint(
    clinic_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    date: date | None = Query(None, description="Filter by appointment date"),
    appointment_status: Optional[str] = Query(None, description="Filter by appointment status"),
    consultation_type: Optional[str] = Query(None, description="Filter by consultation type"),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("clinic_admin", "admin")),
) -> ClinicAppointmentListPaginatedResponse:
    clinic = get_clinic_by_id(db, str(clinic_id))
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found.")

    if _user["role"] == "clinic_admin":
        assigned_clinic_id = get_clinic_admin_clinic_id(db, _user["sub"])
        if not assigned_clinic_id or str(assigned_clinic_id) != str(clinic_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Clinic admin is not permitted to view appointments for this clinic.",
            )

    return ClinicAppointmentListPaginatedResponse.model_validate(
        get_clinic_appointments(
            clinic_id=clinic_id,
            page=page,
            size=size,
            target_date=date,
            status_filter=appointment_status,
            consultation_type=consultation_type,
        )
    )


@router.patch("/{clinic_id}", response_model=ClinicResponse)
def update_clinic_endpoint(
    clinic_id: str,
    payload: UpdateClinicRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("clinic_admin", "admin")),
) -> ClinicResponse:
    if _user["role"] == "clinic_admin":
        assigned_clinic_id = get_clinic_admin_clinic_id(db, _user["sub"])
        if not assigned_clinic_id or str(assigned_clinic_id) != str(clinic_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Clinic admin is not permitted to update this clinic.",
            )
    clinic = update_clinic(
        db=db,
        clinic_id=clinic_id,
        payload=payload,
        changed_by=_user["sub"],
    )
    return ClinicResponse.model_validate(clinic)


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
