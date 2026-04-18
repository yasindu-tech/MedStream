from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Clinic, Doctor, DoctorClinicAssignment
from app.services.appointment_client import (
    get_clinic_operational_dashboard,
    get_platform_active_patients_count,
    get_platform_daily_bookings_count,
)
from app.services.payment_client import get_clinic_payment_summary, get_platform_payment_summary


def count_active_clinic_doctors(db: Session, clinic_id: str) -> int:
    return (
        db.query(DoctorClinicAssignment.doctor_id)
        .join(Doctor, Doctor.doctor_id == DoctorClinicAssignment.doctor_id)
        .join(Clinic, Clinic.clinic_id == DoctorClinicAssignment.clinic_id)
        .filter(
            DoctorClinicAssignment.clinic_id == clinic_id,
            DoctorClinicAssignment.status == "active",
            Doctor.status == "active",
            Clinic.status == "active",
        )
        .distinct()
        .count()
    )


def count_active_doctors(db: Session) -> int:
    return (
        db.query(DoctorClinicAssignment.doctor_id)
        .join(Doctor, Doctor.doctor_id == DoctorClinicAssignment.doctor_id)
        .join(Clinic, Clinic.clinic_id == DoctorClinicAssignment.clinic_id)
        .filter(
            DoctorClinicAssignment.status == "active",
            Doctor.status == "active",
            Clinic.status == "active",
        )
        .distinct()
        .count()
    )


def count_active_clinics(db: Session) -> int:
    return db.query(Clinic).filter(Clinic.status == "active").count()


def build_clinic_dashboard(db: Session, clinic_id: str) -> dict:
    warnings: list[str] = []
    active_doctors = count_active_clinic_doctors(db, clinic_id)

    try:
        dashboard = get_clinic_operational_dashboard(clinic_id)
    except HTTPException as exc:
        if exc.status_code in (status.HTTP_502_BAD_GATEWAY, status.HTTP_503_SERVICE_UNAVAILABLE):
            warnings.append("Appointment service unavailable for clinic operational data.")
            dashboard = {
                "total_appointments": 0,
                "completed_consultations": 0,
                "cancellations": 0,
                "patients_in_queue": 0,
                "doctor_appointment_counts": [],
            }
        else:
            raise

    doctor_specializations = {}
    doctor_ids = [row.get("doctor_id") for row in dashboard.get("doctor_appointment_counts", []) if row.get("doctor_id")]
    if doctor_ids:
        doctor_rows = (
            db.query(Doctor.doctor_id, Doctor.specialization)
            .filter(Doctor.doctor_id.in_(doctor_ids))
            .all()
        )
        doctor_specializations = {str(row.doctor_id): row.specialization for row in doctor_rows}

    try:
        payment_summary = get_clinic_payment_summary(clinic_id)
    except HTTPException as exc:
        if exc.status_code in (status.HTTP_502_BAD_GATEWAY, status.HTTP_503_SERVICE_UNAVAILABLE):
            warnings.append("Payment service unavailable for clinic financial summary.")
            payment_summary = {
                "total_revenue": 0,
                "total_refunded": 0,
                "total_failed": 0,
                "clinic_share_total": 0,
                "period_start": None,
                "period_end": None,
            }
        else:
            raise

    return {
        "clinic_id": clinic_id,
        "active_doctors": active_doctors,
        "total_appointments": int(dashboard.get("total_appointments", 0)),
        "completed_consultations": int(dashboard.get("completed_consultations", 0)),
        "cancellations": int(dashboard.get("cancellations", 0)),
        "patients_in_queue": int(dashboard.get("patients_in_queue", 0)),
        "doctor_appointment_counts": [
            {
                "doctor_id": row.get("doctor_id"),
                "doctor_name": row.get("doctor_name"),
                "specialty": doctor_specializations.get(str(row.get("doctor_id"))) if row.get("doctor_id") else None,
                "appointment_count": int(row.get("appointment_count", 0)),
            }
            for row in dashboard.get("doctor_appointment_counts", [])
        ],
        "payment_summary": payment_summary,
        "warnings": warnings,
    }


def build_platform_summary(db: Session, target_date: date | None = None) -> dict:
    warnings: list[str] = []
    total_clinics = count_active_clinics(db)
    active_doctors = count_active_doctors(db)

    try:
        active_patients = get_platform_active_patients_count()
    except HTTPException as exc:
        if exc.status_code in (status.HTTP_502_BAD_GATEWAY, status.HTTP_503_SERVICE_UNAVAILABLE):
            warnings.append("Appointment service unavailable for active patient count.")
            active_patients = 0
        else:
            raise

    try:
        daily_bookings = get_platform_daily_bookings_count(target_date.isoformat() if target_date else None)
    except HTTPException as exc:
        if exc.status_code in (status.HTTP_502_BAD_GATEWAY, status.HTTP_503_SERVICE_UNAVAILABLE):
            warnings.append("Appointment service unavailable for daily booking counts.")
            daily_bookings = 0
        else:
            raise

    try:
        payment_summary = get_platform_payment_summary()
    except HTTPException as exc:
        if exc.status_code in (status.HTTP_502_BAD_GATEWAY, status.HTTP_503_SERVICE_UNAVAILABLE):
            warnings.append("Payment service unavailable for platform payment summary.")
            payment_summary = {
                "total_revenue": 0,
                "total_refunded": 0,
                "total_failed": 0,
                "total_pending": 0,
                "platform_commission_total": 0,
                "payment_count": 0,
                "refund_count": 0,
            }
        else:
            raise

    return {
        "total_clinics": total_clinics,
        "active_doctors": active_doctors,
        "active_patients": active_patients,
        "daily_bookings": daily_bookings,
        "payment_summary": payment_summary,
        "warnings": warnings,
    }
