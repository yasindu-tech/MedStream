from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Allergy, ChronicCondition, ConsultationSummary, MedicalDocument, Patient, Prescription
from app.schemas import (
    ConsultationSummaryResponse,
    ConsultationSummaryUpsertRequest,
    InternalPatientMedicalSummaryResponse,
    PatientProfileCreate,
    PatientProfileResponse,
)

router = APIRouter(tags=["internal"])


@router.post("/patients", response_model=PatientProfileResponse, status_code=201)
def create_patient_profile(request: PatientProfileCreate, db: Session = Depends(get_db)) -> PatientProfileResponse:
    existing_by_user = db.query(Patient).filter(Patient.user_id == request.user_id).first()
    if existing_by_user:
        return existing_by_user

    existing_by_email = db.query(Patient).filter(Patient.email == request.email).first()
    if existing_by_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A patient profile already exists for this email.",
        )

    full_name = request.full_name or Patient.build_full_name(request.email)
    patient = Patient(
        user_id=request.user_id,
        email=request.email,
        phone=request.phone,
        full_name=full_name,
        dob=request.dob,
        gender=request.gender,
        nic_passport=request.nic_passport,
        profile_status="active",
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/patients/{patient_id}/medical-summary", response_model=InternalPatientMedicalSummaryResponse)
def get_internal_patient_medical_summary(
    patient_id: UUID,
    db: Session = Depends(get_db),
) -> InternalPatientMedicalSummaryResponse:
    patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")

    allergies = (
        db.query(Allergy)
        .filter(Allergy.patient_id == patient.patient_id)
        .order_by(Allergy.allergy_name.asc())
        .all()
    )
    chronic_conditions = (
        db.query(ChronicCondition)
        .filter(ChronicCondition.patient_id == patient.patient_id)
        .order_by(ChronicCondition.condition_name.asc())
        .all()
    )
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient.patient_id)
        .order_by(Prescription.created_at.desc())
        .limit(20)
        .all()
    )
    documents = (
        db.query(MedicalDocument)
        .filter(MedicalDocument.patient_id == patient.patient_id)
        .order_by(MedicalDocument.uploaded_at.desc())
        .limit(20)
        .all()
    )

    return InternalPatientMedicalSummaryResponse(
        profile=patient,
        allergies=allergies,
        chronic_conditions=chronic_conditions,
        prescriptions=prescriptions,
        documents=documents,
    )


@router.post("/patients/{patient_id}/consultation-summaries", response_model=ConsultationSummaryResponse)
def upsert_internal_consultation_summary(
    patient_id: UUID,
    request: ConsultationSummaryUpsertRequest,
    db: Session = Depends(get_db),
) -> ConsultationSummaryResponse:
    patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")

    summary = (
        db.query(ConsultationSummary)
        .filter(ConsultationSummary.appointment_id == request.appointment_id)
        .first()
    )
    if not summary:
        summary = ConsultationSummary(
            appointment_id=request.appointment_id,
            patient_id=patient_id,
        )
        db.add(summary)

    summary.status = request.status
    summary.llm_used = request.llm_used
    summary.doctor_name = request.doctor_name
    summary.diagnosis = request.diagnosis
    summary.medications = request.medications
    summary.sections = request.sections
    summary.summary_text = request.summary_text
    summary.summary_html = request.summary_html
    summary.missing_fields = request.missing_fields
    summary.warnings = request.warnings
    summary.generated_at = request.generated_at or summary.generated_at

    db.commit()
    db.refresh(summary)
    return summary
