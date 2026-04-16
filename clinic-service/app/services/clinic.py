import logging
import secrets
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Clinic, ClinicAdmin
from app.schemas import CreateClinicRequest
from app.services.auth_client import register_clinic_admin_user
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


def list_clinics(db: Session) -> list[Clinic]:
    return db.query(Clinic).order_by(Clinic.created_at.desc()).all()
