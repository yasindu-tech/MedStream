import logging
import secrets
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    Clinic,
    ClinicAdmin,
    ClinicStaff,
    ClinicStatusHistory,
    Doctor,
    DoctorClinicAssignment,
)
from app.schemas import CreateClinicRequest
from app.services.appointment_client import get_clinic_future_appointments_count
from app.services.auth_client import deactivate_clinic_admin_user, register_clinic_admin_user
from app.services.notification_client import queue_clinic_admin_onboarding_email

logger = logging.getLogger(__name__)


def _generate_temporary_password() -> str:
    return secrets.token_urlsafe(12)


def get_clinic_by_registration(db: Session, registration_no: str) -> Clinic | None:
    return (
        db.query(Clinic)
        .filter(Clinic.registration_no == registration_no)
        .first()
    )


def get_clinic_by_email(db: Session, email: str) -> Clinic | None:
    return db.query(Clinic).filter(Clinic.email == email).first()


def get_clinic_by_id(db: Session, clinic_id: str | None) -> Clinic | None:
    if not clinic_id:
        return None
    return db.query(Clinic).filter(Clinic.clinic_id == clinic_id).first()


def _log_clinic_status_change(
    db: Session,
    clinic: Clinic,
    new_status: str,
    changed_by: str | None = None,
    reason: str | None = None,
) -> None:
    history = ClinicStatusHistory(
        clinic_id=clinic.clinic_id,
        old_status=clinic.status,
        new_status=new_status,
        changed_by=changed_by,
        reason=reason,
    )
    db.add(history)


def change_clinic_status(
    db: Session,
    clinic_id: str,
    new_status: str,
    changed_by: str | None = None,
    reason: str | None = None,
) -> Clinic:
    if new_status not in ("active", "inactive"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid clinic status. Allowed values are 'active' and 'inactive'.",
        )

    clinic = get_clinic_by_id(db, clinic_id)
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found.")

    if clinic.status == "removed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Removed clinics cannot be reactivated.",
        )

    if clinic.status == new_status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Clinic is already {new_status}.",
        )

    old_status = clinic.status
    clinic.status = new_status
    db.add(clinic)
    _log_clinic_status_change(db, clinic, new_status, changed_by=changed_by, reason=reason)
    db.commit()
    db.refresh(clinic)

    logger.info(
        "Clinic %s status changed from %s to %s by %s",
        clinic.clinic_id,
        old_status,
        new_status,
        changed_by or "system",
    )
    return clinic


def remove_clinic(
    db: Session,
    clinic_id: str,
    changed_by: str | None = None,
    reason: str | None = None,
) -> Clinic:
    clinic = get_clinic_by_id(db, clinic_id)
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found.")

    if clinic.status == "removed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Clinic is already removed.",
        )

    future_count = get_clinic_future_appointments_count(clinic.clinic_id)
    if future_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Clinic cannot be removed because it has pending future appointments.",
        )

    active_doctor_count = (
        db.query(DoctorClinicAssignment)
        .join(Doctor, Doctor.doctor_id == DoctorClinicAssignment.doctor_id)
        .filter(
            DoctorClinicAssignment.clinic_id == clinic.clinic_id,
            DoctorClinicAssignment.status == "active",
            Doctor.status == "active",
        )
        .count()
    )
    if active_doctor_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Clinic cannot be removed because active doctors are still assigned.",
        )

    clinic.status = "removed"
    db.add(clinic)

    admin_user_ids = [
        admin.user_id
        for admin in db.query(ClinicAdmin).filter(ClinicAdmin.clinic_id == clinic.clinic_id).all()
        if admin.user_id
    ]
    db.query(ClinicAdmin).filter(ClinicAdmin.clinic_id == clinic.clinic_id).update(
        {"status": "inactive"}, synchronize_session=False
    )
    db.query(ClinicStaff).filter(ClinicStaff.clinic_id == clinic.clinic_id).update(
        {"status": "inactive"}, synchronize_session=False
    )
    _log_clinic_status_change(db, clinic, "removed", changed_by=changed_by, reason=reason)
    db.commit()
    db.refresh(clinic)

    for user_id in admin_user_ids:
        try:
            deactivate_clinic_admin_user(str(user_id))
        except HTTPException as exc:
            logger.warning(
                "Could not deactivate clinic admin %s in auth service: %s",
                user_id,
                exc.detail,
            )

    logger.info(
        "Clinic %s removed by %s",
        clinic.clinic_id,
        changed_by or "system",
    )
    return clinic


def list_clinics(db: Session, active_only: bool = False) -> list[Clinic]:
    query = db.query(Clinic).order_by(Clinic.created_at.desc())
    if active_only:
        query = query.filter(Clinic.status == "active")
    return query.all()


def create_clinic(db: Session, payload: CreateClinicRequest) -> Clinic:
    if get_clinic_by_registration(db, payload.registration_no):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Clinic registration number already exists.",
        )

    if get_clinic_by_email(db, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Clinic email is already in use.",
        )

    temp_password = _generate_temporary_password()
    clinic = Clinic(
        clinic_name=payload.clinic_name,
        registration_no=payload.registration_no,
        address=payload.address,
        phone=payload.phone,
        email=payload.email,
        status="inactive",
    )

    db.add(clinic)
    db.flush()

    try:
        auth_user = register_clinic_admin_user(
            email=payload.email,
            password=temp_password,
            phone=payload.phone,
        )
    except HTTPException:
        db.rollback()
        raise

    onboarding = ClinicAdmin(
        clinic_id=clinic.clinic_id,
        user_id=auth_user["id"],
        status="pending",
    )
    db.add(onboarding)
    db.commit()
    db.refresh(clinic)

    try:
        queue_clinic_admin_onboarding_email(
            user_id=auth_user["id"],
            email=payload.email,
            clinic_name=payload.clinic_name,
            temporary_password=temp_password,
        )
    except HTTPException as exc:
        logger.warning(
            "Clinic created but onboarding email could not be queued: %s",
            exc.detail,
        )

    return clinic
