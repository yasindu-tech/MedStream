import logging
import secrets
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    Clinic,
    ClinicAdmin,
    ClinicStaff,
    ClinicStaffHistory,
    ClinicStatusHistory,
    Doctor,
    DoctorClinicAssignment,
)
from app.schemas import CreateClinicRequest, CreateClinicStaffRequest, UpdateClinicStaffRequest
from app.services.appointment_client import get_clinic_future_appointments_count
from app.services.auth_client import (
    deactivate_clinic_admin_user,
    deactivate_clinic_staff_user,
    register_clinic_admin_user,
    register_clinic_staff_user,
)
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


def _log_clinic_staff_history(
    db: Session,
    staff: ClinicStaff,
    action: str,
    changed_by: str | None = None,
) -> None:
    history = ClinicStaffHistory(
        staff_id=staff.staff_id,
        clinic_id=staff.clinic_id,
        user_id=staff.user_id,
        staff_email=staff.staff_email,
        staff_name=staff.staff_name,
        staff_phone=staff.staff_phone,
        staff_role=staff.staff_role,
        status=staff.status,
        action=action,
        changed_by=changed_by,
    )
    db.add(history)


def get_clinic_admin_clinic_id(db: Session, user_id: str) -> str | None:
    admin = (
        db.query(ClinicAdmin)
        .filter(ClinicAdmin.user_id == user_id, ClinicAdmin.status == "active")
        .first()
    )
    return str(admin.clinic_id) if admin else None


def get_clinic_staff_by_id(db: Session, clinic_id: str, staff_id: str) -> ClinicStaff | None:
    return (
        db.query(ClinicStaff)
        .filter(
            ClinicStaff.clinic_id == clinic_id,
            ClinicStaff.staff_id == staff_id,
        )
        .first()
    )


def list_clinic_staff(db: Session, clinic_id: str, active_only: bool = True) -> list[ClinicStaff]:
    query = db.query(ClinicStaff).filter(ClinicStaff.clinic_id == clinic_id)
    if active_only:
        query = query.filter(ClinicStaff.status == "active")
    return query.order_by(ClinicStaff.created_at.desc()).all()


def create_clinic_staff(
    db: Session,
    clinic_id: str,
    payload: CreateClinicStaffRequest,
    created_by: str | None = None,
) -> dict:
    clinic = get_clinic_by_id(db, clinic_id)
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found.")
    if clinic.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff cannot be added to an inactive clinic.",
        )

    temp_password = _generate_temporary_password()
    try:
        auth_user = register_clinic_staff_user(
            email=payload.email,
            password=temp_password,
            phone=payload.phone,
        )
    except HTTPException:
        raise

    staff = ClinicStaff(
        clinic_id=clinic.clinic_id,
        user_id=auth_user["id"],
        staff_email=auth_user["email"],
        staff_name=payload.name,
        staff_phone=payload.phone,
        staff_role=payload.role,
        status="active",
    )
    db.add(staff)
    db.flush()
    _log_clinic_staff_history(db, staff, action="created", changed_by=created_by)
    db.commit()
    db.refresh(staff)

    return {"staff": staff, "temporary_password": temp_password}


def update_clinic_staff(
    db: Session,
    clinic_id: str,
    staff_id: str,
    payload: UpdateClinicStaffRequest,
    changed_by: str | None = None,
) -> ClinicStaff:
    staff = get_clinic_staff_by_id(db, clinic_id, staff_id)
    if not staff or staff.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic staff not found.")

    changes = False
    if payload.name is not None:
        staff.staff_name = payload.name
        changes = True
    if payload.phone is not None:
        staff.staff_phone = payload.phone
        changes = True
    if payload.role is not None:
        staff.staff_role = payload.role
        changes = True

    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid updates provided.")

    staff.updated_at = datetime.utcnow()
    staff.updated_by = changed_by
    _log_clinic_staff_history(db, staff, action="updated", changed_by=changed_by)
    db.commit()
    db.refresh(staff)
    return staff


def remove_clinic_staff(
    db: Session,
    clinic_id: str,
    staff_id: str,
    changed_by: str | None = None,
) -> ClinicStaff:
    staff = get_clinic_staff_by_id(db, clinic_id, staff_id)
    if not staff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic staff not found.")
    if staff.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Clinic staff is already inactive.")

    staff.status = "inactive"
    staff.updated_at = datetime.utcnow()
    staff.updated_by = changed_by
    _log_clinic_staff_history(db, staff, action="removed", changed_by=changed_by)

    try:
        deactivate_clinic_staff_user(str(staff.user_id))
    except HTTPException:
        db.rollback()
        raise

    db.commit()
    db.refresh(staff)
    return staff
