from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import (
    AvailableDoctorResponse,
    ClinicDoctorResponse,
    DoctorAssignmentRequest,
)
from app.services.clinic import (
    create_clinic_doctor_assignment,
    get_clinic_admin_clinic_id,
    get_clinic_doctor_assignment,
    list_available_doctors_for_assignment,
    list_clinic_doctor_assignments,
    remove_clinic_doctor_assignment,
    get_clinic_by_id,
)
from app.models import Doctor

router = APIRouter(tags=["Clinic Doctor Assignments"])


def _ensure_clinic_admin_scope(db: Session, user: dict, clinic_id: UUID) -> None:
    if user["role"] != "clinic_admin":
        return

    assigned_clinic_id = get_clinic_admin_clinic_id(db, user["sub"])
    if not assigned_clinic_id or str(assigned_clinic_id) != str(clinic_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clinic admin is not permitted to manage this clinic",
        )


@router.get("/{clinic_id}/doctors/available", response_model=List[AvailableDoctorResponse])
def list_available_doctors_endpoint(
    clinic_id: UUID,
    specialty: str | None = Query(None, description="Filter by specialization"),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("clinic_admin", "admin")),
) -> List[AvailableDoctorResponse]:
    doctors = list_available_doctors_for_assignment(db=db, clinic_id=str(clinic_id), specialty=specialty)
    return [AvailableDoctorResponse.model_validate(doctor) for doctor in doctors]


@router.post("/{clinic_id}/doctors", response_model=ClinicDoctorResponse, status_code=status.HTTP_201_CREATED)
def assign_doctor_to_clinic_endpoint(
    clinic_id: UUID,
    payload: DoctorAssignmentRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("clinic_admin", "admin")),
) -> ClinicDoctorResponse:
    _ensure_clinic_admin_scope(db, _user, clinic_id)
    assignment = create_clinic_doctor_assignment(
        db=db,
        clinic_id=str(clinic_id),
        doctor_id=str(payload.doctor_id),
        changed_by=_user["sub"],
    )

    doctor = db.query(Doctor).filter(Doctor.doctor_id == payload.doctor_id).first()
    return ClinicDoctorResponse(
        assignment_id=assignment.assignment_id,
        clinic_id=assignment.clinic_id,
        doctor_id=assignment.doctor_id,
        full_name=doctor.full_name if doctor else "",
        medical_registration_no=doctor.medical_registration_no if doctor else None,
        specialization=doctor.specialization if doctor else None,
        consultation_mode=doctor.consultation_mode if doctor else None,
        consultation_fee=float(doctor.consultation_fee) if doctor and doctor.consultation_fee is not None else None,
        verification_status=doctor.verification_status if doctor else "",
        doctor_status=doctor.status if doctor else "",
        assignment_status=assignment.status,
    )


@router.get("/{clinic_id}/doctors", response_model=List[ClinicDoctorResponse])
def list_clinic_doctors_endpoint(
    clinic_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("clinic_admin", "admin")),
) -> List[ClinicDoctorResponse]:
    _ensure_clinic_admin_scope(db, _user, clinic_id)
    clinic = get_clinic_by_id(db, str(clinic_id))
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found.")

    assignments = list_clinic_doctor_assignments(db=db, clinic_id=str(clinic_id))
    result: list[ClinicDoctorResponse] = []
    for assignment in assignments:
        doctor = db.query(Doctor).filter(Doctor.doctor_id == assignment.doctor_id).first()
        result.append(
            ClinicDoctorResponse(
                assignment_id=assignment.assignment_id,
                clinic_id=assignment.clinic_id,
                doctor_id=assignment.doctor_id,
                full_name=doctor.full_name if doctor else "",
                medical_registration_no=doctor.medical_registration_no if doctor else None,
                specialization=doctor.specialization if doctor else None,
                consultation_mode=doctor.consultation_mode if doctor else None,
                consultation_fee=float(doctor.consultation_fee) if doctor and doctor.consultation_fee is not None else None,
                verification_status=doctor.verification_status if doctor else "",
                doctor_status=doctor.status if doctor else "",
                assignment_status=assignment.status,
            )
        )
    return result


@router.delete("/{clinic_id}/doctors/{doctor_id}", response_model=ClinicDoctorResponse)
def remove_doctor_from_clinic_endpoint(
    clinic_id: UUID,
    doctor_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles("clinic_admin", "admin")),
) -> ClinicDoctorResponse:
    _ensure_clinic_admin_scope(db, _user, clinic_id)
    assignment = remove_clinic_doctor_assignment(
        db=db,
        clinic_id=str(clinic_id),
        doctor_id=str(doctor_id),
        changed_by=_user["sub"],
    )

    doctor = db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()
    return ClinicDoctorResponse(
        assignment_id=assignment.assignment_id,
        clinic_id=assignment.clinic_id,
        doctor_id=assignment.doctor_id,
        full_name=doctor.full_name if doctor else "",
        medical_registration_no=doctor.medical_registration_no if doctor else None,
        specialization=doctor.specialization if doctor else None,
        consultation_mode=doctor.consultation_mode if doctor else None,
        consultation_fee=float(doctor.consultation_fee) if doctor and doctor.consultation_fee is not None else None,
        verification_status=doctor.verification_status if doctor else "",
        doctor_status=doctor.status if doctor else "",
        assignment_status=assignment.status,
    )
