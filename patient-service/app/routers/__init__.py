from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Allergy, ChronicCondition, ConsultationSummary, MedicalDocument, Patient, Prescription
from app.schemas import (
    AllergyCreate,
    AllergyResponse,
    AllergyUpdate,
    ConsultationSummaryResponse,
    ChronicConditionCreate,
    ChronicConditionResponse,
    ChronicConditionUpdate,
    MedicalDocumentResponse,
    MedicalDocumentUpdate,
    PatientMedicalSummaryResponse,
    PatientProfilePageResponse,
    PatientPrescriptionCreate,
    PatientPrescriptionResponse,
    PatientProfileResponse,
    PatientProfileUpdate,
)
from app.services.document_storage import MAX_DOCUMENT_SIZE_BYTES, delete_patient_document, upload_patient_document
from app.services.notification_client import send_in_app_notification

router = APIRouter(tags=["Patient Profiles"])

ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_DOCUMENT_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}


def _get_patient_or_404(db: Session, patient_id: UUID) -> Patient:
    patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")
    return patient


def _emit_patient_event(patient: Patient, event_type: str, payload: dict[str, Any]) -> None:
    if not patient.user_id:
        return
    send_in_app_notification(
        event_type=event_type,
        user_id=str(patient.user_id),
        payload=payload,
    )


@router.get("/me", response_model=PatientProfileResponse)
def get_my_patient_profile(user_id: UUID = Query(..., description="Current patient user ID"), db: Session = Depends(get_db)) -> PatientProfileResponse:
    patient = db.query(Patient).filter(Patient.user_id == user_id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")
    return patient


@router.get("/by-user/{user_id}", response_model=PatientProfileResponse)
def get_patient_profile_by_user_id(user_id: UUID, db: Session = Depends(get_db)) -> PatientProfileResponse:
    patient = db.query(Patient).filter(Patient.user_id == user_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient


@router.get("/by-user/{user_id}/consultation-summaries", response_model=list[ConsultationSummaryResponse])
def list_consultation_summaries_by_user(user_id: UUID, db: Session = Depends(get_db)) -> list[ConsultationSummaryResponse]:
    patient = db.query(Patient).filter(Patient.user_id == user_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    summaries = (
        db.query(ConsultationSummary)
        .filter(ConsultationSummary.patient_id == patient.patient_id)
        .order_by(ConsultationSummary.generated_at.desc())
        .all()
    )
    return summaries


@router.get("/patients/{patient_id}", response_model=PatientProfileResponse)
def get_patient_profile(patient_id: UUID, db: Session = Depends(get_db)) -> PatientProfileResponse:
    patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient


@router.get("/patients/{patient_id}/consultation-summaries", response_model=list[ConsultationSummaryResponse])
def list_consultation_summaries(patient_id: UUID, db: Session = Depends(get_db)) -> list[ConsultationSummaryResponse]:
    _get_patient_or_404(db, patient_id)
    summaries = (
        db.query(ConsultationSummary)
        .filter(ConsultationSummary.patient_id == patient_id)
        .order_by(ConsultationSummary.generated_at.desc())
        .all()
    )
    return summaries


@router.get("/patients/{patient_id}/medical-summary", response_model=PatientMedicalSummaryResponse)
def get_patient_medical_summary(patient_id: UUID, db: Session = Depends(get_db)) -> PatientMedicalSummaryResponse:
    patient = _get_patient_or_404(db, patient_id)
    
    allergies = (
        db.query(Allergy)
        .filter(Allergy.patient_id == patient_id)
        .order_by(Allergy.allergy_name.asc())
        .all()
    )
    chronic_conditions = (
        db.query(ChronicCondition)
        .filter(ChronicCondition.patient_id == patient_id)
        .order_by(ChronicCondition.condition_name.asc())
        .all()
    )
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient_id)
        .order_by(Prescription.created_at.desc())
        .all()
    )
    documents = (
        db.query(MedicalDocument)
        .filter(MedicalDocument.patient_id == patient_id)
        .order_by(MedicalDocument.uploaded_at.desc())
        .all()
    )
    consultation_summaries = (
        db.query(ConsultationSummary)
        .filter(ConsultationSummary.patient_id == patient_id)
        .order_by(ConsultationSummary.generated_at.desc())
        .all()
    )

    return PatientMedicalSummaryResponse(
        profile=patient,
        allergies=allergies,
        chronic_conditions=chronic_conditions,
        prescriptions=prescriptions,
        documents=documents,
        consultation_summaries=consultation_summaries,
    )


@router.patch("/patients/{patient_id}", response_model=PatientProfilePageResponse)
def update_patient_profile(patient_id: UUID, request: PatientProfileUpdate, db: Session = Depends(get_db)) -> PatientProfilePageResponse:
    patient = _get_patient_or_404(db, patient_id)

    updated_fields: list[str] = []

    if request.nic_passport is not None and request.nic_passport != patient.nic_passport:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="NIC/passport changes require admin approval.",
        )

    if request.full_name is not None:
        patient.full_name = request.full_name
        updated_fields.append("full_name")

    if request.dob is not None:
        patient.dob = request.dob
        updated_fields.append("dob")

    if request.gender is not None:
        patient.gender = request.gender
        updated_fields.append("gender")

    if request.address is not None:
        patient.address = request.address
        updated_fields.append("address")

    if request.phone is not None:
        patient.phone = request.phone
        updated_fields.append("phone")

    if request.emergency_contact is not None:
        patient.emergency_contact = request.emergency_contact
        updated_fields.append("emergency_contact")

    if request.profile_image_url is not None:
        patient.profile_image_url = request.profile_image_url
        updated_fields.append("profile_image_url")

    if request.blood_group is not None:
        patient.blood_group = request.blood_group
        updated_fields.append("blood_group")

    db.commit()
    db.refresh(patient)

    if updated_fields:
        _emit_patient_event(
            patient,
            event_type="patient.profile.updated",
            payload={
                "patient_id": str(patient.patient_id),
                "patient_name": patient.full_name,
                "updated_fields": ", ".join(updated_fields),
            },
        )

    return patient


@router.get("/patients/{patient_id}/allergies", response_model=list[AllergyResponse])
def list_patient_allergies(patient_id: UUID, db: Session = Depends(get_db)) -> list[AllergyResponse]:
    _get_patient_or_404(db, patient_id)
    allergies = (
        db.query(Allergy)
        .filter(Allergy.patient_id == patient_id)
        .order_by(Allergy.allergy_name.asc())
        .all()
    )
    return allergies


@router.post("/patients/{patient_id}/allergies", response_model=AllergyResponse, status_code=status.HTTP_201_CREATED)
def create_patient_allergy(patient_id: UUID, request: AllergyCreate, db: Session = Depends(get_db)) -> AllergyResponse:
    patient = _get_patient_or_404(db, patient_id)
    allergy = Allergy(
        patient_id=patient_id,
        allergy_name=request.allergy_name,
        note=request.note,
    )
    db.add(allergy)
    db.commit()
    db.refresh(allergy)

    _emit_patient_event(
        patient,
        event_type="patient.medical_info.updated",
        payload={
            "patient_id": str(patient.patient_id),
            "patient_name": patient.full_name,
            "section": "allergy",
            "action": "created",
            "item_name": allergy.allergy_name,
        },
    )

    return allergy


@router.patch("/patients/{patient_id}/allergies/{allergy_id}", response_model=AllergyResponse)
def update_patient_allergy(
    patient_id: UUID,
    allergy_id: UUID,
    request: AllergyUpdate,
    db: Session = Depends(get_db),
) -> AllergyResponse:
    patient = _get_patient_or_404(db, patient_id)
    allergy = (
        db.query(Allergy)
        .filter(Allergy.allergy_id == allergy_id, Allergy.patient_id == patient_id)
        .first()
    )
    if not allergy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allergy not found")

    if request.allergy_name is not None:
        allergy.allergy_name = request.allergy_name
    if request.note is not None:
        allergy.note = request.note

    db.commit()
    db.refresh(allergy)

    _emit_patient_event(
        patient,
        event_type="patient.medical_info.updated",
        payload={
            "patient_id": str(patient.patient_id),
            "patient_name": patient.full_name,
            "section": "allergy",
            "action": "updated",
            "item_name": allergy.allergy_name,
        },
    )

    return allergy


@router.delete("/patients/{patient_id}/allergies/{allergy_id}")
def delete_patient_allergy(patient_id: UUID, allergy_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    patient = _get_patient_or_404(db, patient_id)
    allergy = (
        db.query(Allergy)
        .filter(Allergy.allergy_id == allergy_id, Allergy.patient_id == patient_id)
        .first()
    )
    if not allergy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allergy not found")

    allergy_name = allergy.allergy_name
    db.delete(allergy)
    db.commit()

    _emit_patient_event(
        patient,
        event_type="patient.medical_info.updated",
        payload={
            "patient_id": str(patient.patient_id),
            "patient_name": patient.full_name,
            "section": "allergy",
            "action": "deleted",
            "item_name": allergy_name,
        },
    )

    return {"message": "Allergy deleted"}


@router.get("/patients/{patient_id}/chronic-diseases", response_model=list[ChronicConditionResponse])
def list_patient_chronic_diseases(patient_id: UUID, db: Session = Depends(get_db)) -> list[ChronicConditionResponse]:
    _get_patient_or_404(db, patient_id)
    conditions = (
        db.query(ChronicCondition)
        .filter(ChronicCondition.patient_id == patient_id)
        .order_by(ChronicCondition.condition_name.asc())
        .all()
    )
    return conditions


@router.post(
    "/patients/{patient_id}/chronic-diseases",
    response_model=ChronicConditionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_patient_chronic_disease(
    patient_id: UUID,
    request: ChronicConditionCreate,
    db: Session = Depends(get_db),
) -> ChronicConditionResponse:
    patient = _get_patient_or_404(db, patient_id)
    condition = ChronicCondition(
        patient_id=patient_id,
        condition_name=request.condition_name,
        note=request.note,
    )
    db.add(condition)
    db.commit()
    db.refresh(condition)

    _emit_patient_event(
        patient,
        event_type="patient.medical_info.updated",
        payload={
            "patient_id": str(patient.patient_id),
            "patient_name": patient.full_name,
            "section": "chronic_condition",
            "action": "created",
            "item_name": condition.condition_name,
        },
    )

    return condition


@router.patch("/patients/{patient_id}/chronic-diseases/{condition_id}", response_model=ChronicConditionResponse)
def update_patient_chronic_disease(
    patient_id: UUID,
    condition_id: UUID,
    request: ChronicConditionUpdate,
    db: Session = Depends(get_db),
) -> ChronicConditionResponse:
    patient = _get_patient_or_404(db, patient_id)
    condition = (
        db.query(ChronicCondition)
        .filter(ChronicCondition.condition_id == condition_id, ChronicCondition.patient_id == patient_id)
        .first()
    )
    if not condition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chronic disease not found")

    if request.condition_name is not None:
        condition.condition_name = request.condition_name
    if request.note is not None:
        condition.note = request.note

    db.commit()
    db.refresh(condition)

    _emit_patient_event(
        patient,
        event_type="patient.medical_info.updated",
        payload={
            "patient_id": str(patient.patient_id),
            "patient_name": patient.full_name,
            "section": "chronic_condition",
            "action": "updated",
            "item_name": condition.condition_name,
        },
    )

    return condition


@router.delete("/patients/{patient_id}/chronic-diseases/{condition_id}")
def delete_patient_chronic_disease(
    patient_id: UUID,
    condition_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    patient = _get_patient_or_404(db, patient_id)
    condition = (
        db.query(ChronicCondition)
        .filter(ChronicCondition.condition_id == condition_id, ChronicCondition.patient_id == patient_id)
        .first()
    )
    if not condition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chronic disease not found")

    condition_name = condition.condition_name
    db.delete(condition)
    db.commit()

    _emit_patient_event(
        patient,
        event_type="patient.medical_info.updated",
        payload={
            "patient_id": str(patient.patient_id),
            "patient_name": patient.full_name,
            "section": "chronic_condition",
            "action": "deleted",
            "item_name": condition_name,
        },
    )

    return {"message": "Chronic disease deleted"}


@router.get("/patients/{patient_id}/prescriptions", response_model=list[PatientPrescriptionResponse])
def list_patient_prescriptions(patient_id: UUID, db: Session = Depends(get_db)) -> list[PatientPrescriptionResponse]:
    _get_patient_or_404(db, patient_id)
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient_id)
        .order_by(Prescription.created_at.desc())
        .all()
    )
    return prescriptions


@router.post("/patients/{patient_id}/prescriptions", response_model=PatientPrescriptionResponse, status_code=status.HTTP_201_CREATED)
def create_patient_prescription(
    patient_id: UUID,
    request: PatientPrescriptionCreate,
    db: Session = Depends(get_db),
) -> PatientPrescriptionResponse:
    patient = _get_patient_or_404(db, patient_id)
    prescription = Prescription(
        appointment_id=request.appointment_id,
        patient_id=patient_id,
        doctor_id=request.doctor_id,
        clinic_id=request.clinic_id,
        medications=request.medications,
        instructions=request.instructions,
        status=request.status,
        issued_at=request.issued_at or datetime.now(),
        finalized_at=request.finalized_at,
    )
    db.add(prescription)
    db.commit()
    db.refresh(prescription)

    _emit_patient_event(
        patient,
        event_type="patient.medical_info.updated",
        payload={
            "patient_id": str(patient.patient_id),
            "patient_name": patient.full_name,
            "section": "prescription",
            "action": "created",
            "item_name": "prescription",
        },
    )

    return prescription


@router.delete("/patients/{patient_id}/prescriptions/{prescription_id}")
def delete_patient_prescription(
    patient_id: UUID,
    prescription_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    patient = _get_patient_or_404(db, patient_id)
    prescription = (
        db.query(Prescription)
        .filter(Prescription.prescription_id == prescription_id, Prescription.patient_id == patient_id)
        .first()
    )
    if not prescription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found")

    db.delete(prescription)
    db.commit()

    _emit_patient_event(
        patient,
        event_type="patient.medical_info.updated",
        payload={
            "patient_id": str(patient.patient_id),
            "patient_name": patient.full_name,
            "section": "prescription",
            "action": "deleted",
            "item_name": "prescription",
        },
    )

    return {"message": "Prescription deleted"}


@router.post("/patients/{patient_id}/documents", response_model=MedicalDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_patient_medical_document(
    patient_id: UUID,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    visibility: str = Form("public"),
    db: Session = Depends(get_db),
) -> MedicalDocumentResponse:
    patient = _get_patient_or_404(db, patient_id)

    normalized_type = document_type.strip()
    if not normalized_type:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Document type is required")

    normalized_visibility = visibility.strip().lower()
    if normalized_visibility not in {"public", "private", "doctor_only"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Visibility must be one of: public, private, doctor_only",
        )

    filename = (file.filename or "document").strip()
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported file type. Allowed: PDF, JPG, JPEG, PNG.",
        )

    if file.content_type not in ALLOWED_DOCUMENT_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported file content type.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded file is empty")
    if len(file_bytes) > MAX_DOCUMENT_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 10MB limit")

    try:
        upload_result = upload_patient_document(file_bytes=file_bytes, filename=filename, patient_id=str(patient_id))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Cloud upload failed") from exc

    document = MedicalDocument(
        patient_id=patient_id,
        document_type=normalized_type,
        file_name=filename,
        file_url=upload_result.get("secure_url") or upload_result.get("url") or "",
        visibility=normalized_visibility,
    )
    if not document.file_url:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Cloud upload did not return URL")

    db.add(document)
    db.commit()
    db.refresh(document)

    _emit_patient_event(
        patient,
        event_type="patient.report.uploaded",
        payload={
            "patient_id": str(patient.patient_id),
            "patient_name": patient.full_name,
            "document_id": str(document.document_id),
            "document_type": document.document_type,
            "file_name": document.file_name,
        },
    )

    return document


@router.get("/patients/{patient_id}/documents", response_model=list[MedicalDocumentResponse])
def list_patient_documents(patient_id: UUID, db: Session = Depends(get_db)) -> list[MedicalDocumentResponse]:
    _get_patient_or_404(db, patient_id)
    documents = (
        db.query(MedicalDocument)
        .filter(MedicalDocument.patient_id == patient_id)
        .order_by(MedicalDocument.uploaded_at.desc())
        .all()
    )
    return documents


@router.patch("/patients/{patient_id}/documents/{document_id}", response_model=MedicalDocumentResponse)
def update_patient_document(
    patient_id: UUID,
    document_id: UUID,
    request: MedicalDocumentUpdate,
    db: Session = Depends(get_db),
) -> MedicalDocumentResponse:
    patient = _get_patient_or_404(db, patient_id)
    document = (
        db.query(MedicalDocument)
        .filter(MedicalDocument.document_id == document_id, MedicalDocument.patient_id == patient_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical document not found")

    if request.document_type is not None:
        document.document_type = request.document_type
    if request.visibility is not None:
        document.visibility = request.visibility

    db.commit()
    db.refresh(document)

    _emit_patient_event(
        patient,
        event_type="patient.report.updated",
        payload={
            "patient_id": str(patient.patient_id),
            "patient_name": patient.full_name,
            "document_id": str(document.document_id),
            "document_type": document.document_type,
            "file_name": document.file_name,
        },
    )

    return document


@router.delete("/patients/{patient_id}/documents/{document_id}")
def delete_patient_document_record(
    patient_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    patient = _get_patient_or_404(db, patient_id)
    document = (
        db.query(MedicalDocument)
        .filter(MedicalDocument.document_id == document_id, MedicalDocument.patient_id == patient_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical document not found")

    file_name = document.file_name
    document_type = document.document_type
    file_url = document.file_url
    db.delete(document)
    db.commit()

    try:
        delete_patient_document(file_url)
    except Exception:
        # Keep DB delete success as authoritative even if cloud cleanup fails.
        pass

    _emit_patient_event(
        patient,
        event_type="patient.report.deleted",
        payload={
            "patient_id": str(patient.patient_id),
            "patient_name": patient.full_name,
            "document_id": str(document_id),
            "document_type": document_type,
            "file_name": file_name,
        },
    )

    return {"message": "Medical document deleted"}
