from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import (
    ClinicAssignmentResponse,
    ClinicStaffResponse,
    CreateClinicStaffRequest,
    CreateClinicStaffResponse,
    UpdateClinicStaffRequest,
)
from app.services.clinic import (
    create_clinic_staff,
    get_clinic_admin_clinic_id,
    get_user_clinic_assignment,
    list_clinic_staff,
    remove_clinic_staff,
    update_clinic_staff,
)

router = APIRouter(tags=["Clinic Staff"])


def _ensure_clinic_admin_scope(db: Session, user: dict, clinic_id: str) -> None:
    if user["role"] != "clinic_admin":
        return

    assigned_clinic_id = get_clinic_admin_clinic_id(db, user["sub"])
    if not assigned_clinic_id or str(assigned_clinic_id) != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clinic admin is not permitted to manage this clinic",
        )


@router.post(
    "/{clinic_id}/staff",
    response_model=CreateClinicStaffResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_clinic_staff_endpoint(
    clinic_id: str,
    payload: CreateClinicStaffRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("clinic_admin", "admin")),
) -> CreateClinicStaffResponse:
    _ensure_clinic_admin_scope(db, _user, clinic_id)
    result = create_clinic_staff(
        db=db,
        clinic_id=clinic_id,
        payload=payload,
        created_by=_user["sub"],
    )

    return CreateClinicStaffResponse(
        staff=ClinicStaffResponse.model_validate(result["staff"]),
        temporary_password=result["temporary_password"],
    )


@router.get("/assignment", response_model=ClinicAssignmentResponse)
def get_user_clinic_assignment_endpoint(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("clinic_admin", "clinic_staff")),
) -> ClinicAssignmentResponse:
    assignment = get_user_clinic_assignment(db, str(_user["sub"]))
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active clinic assignment for user")
    return ClinicAssignmentResponse.model_validate(assignment)


@router.get("/{clinic_id}/staff", response_model=List[ClinicStaffResponse])
def list_clinic_staff_endpoint(
    clinic_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("clinic_admin", "admin")),
) -> List[ClinicStaffResponse]:
    _ensure_clinic_admin_scope(db, _user, clinic_id)
    return [
        ClinicStaffResponse.model_validate(staff)
        for staff in list_clinic_staff(db=db, clinic_id=clinic_id)
    ]


@router.patch("/{clinic_id}/staff/{staff_id}", response_model=ClinicStaffResponse)
def update_clinic_staff_endpoint(
    clinic_id: str,
    staff_id: UUID,
    payload: UpdateClinicStaffRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("clinic_admin", "admin")),
) -> ClinicStaffResponse:
    _ensure_clinic_admin_scope(db, _user, clinic_id)
    staff = update_clinic_staff(
        db=db,
        clinic_id=clinic_id,
        staff_id=staff_id,
        payload=payload,
        changed_by=_user["sub"],
    )
    return ClinicStaffResponse.model_validate(staff)


@router.delete("/{clinic_id}/staff/{staff_id}", response_model=ClinicStaffResponse)
def remove_clinic_staff_endpoint(
    clinic_id: str,
    staff_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("clinic_admin", "admin")),
) -> ClinicStaffResponse:
    _ensure_clinic_admin_scope(db, _user, clinic_id)
    staff = remove_clinic_staff(
        db=db,
        clinic_id=clinic_id,
        staff_id=staff_id,
        changed_by=_user["sub"],
    )
    return ClinicStaffResponse.model_validate(staff)
