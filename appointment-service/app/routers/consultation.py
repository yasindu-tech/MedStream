"""Doctor consultation workflow endpoints."""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.schemas import (
    AppointmentActionRequest,
    AppointmentListPaginatedResponse,
    AppointmentNoteRequest,
    AppointmentNoteResponse,
    AppointmentOutcomeResponse,
    BookAppointmentResponse,
    PatientDocumentRequest,
    PatientDocumentResponse,
    PatientDocumentsResponse,
    PatientSummaryResponse,
    PrescriptionRequest,
    PrescriptionResponse,
)
from app.services.consultation import (
    create_appointment_note,
    create_patient_document,
    doctor_accept_appointment,
    doctor_reject_appointment,
    finalize_prescription,
    get_patient_summary,
    list_appointment_notes,
    list_patient_documents,
    list_prescriptions,
    create_prescription,
    update_prescription,
)
from app.services.history import fetch_appointment_history

router = APIRouter(tags=["Consultation"], prefix="/appointments")


@router.post("/{appointment_id}/accept", response_model=AppointmentOutcomeResponse)
def accept_appointment_request(
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> AppointmentOutcomeResponse:
    appt = doctor_accept_appointment(db, appointment_id=appointment_id, doctor_user_id=user["sub"])
    return AppointmentOutcomeResponse(
        appointment_id=appt.appointment_id,
        status=appt.status,
        changed_at=datetime.now().isoformat(),
        message="Appointment accepted successfully.",
    )


@router.post("/{appointment_id}/reject", response_model=AppointmentOutcomeResponse)
def reject_appointment_request(
    request: AppointmentActionRequest,
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> AppointmentOutcomeResponse:
    appt = doctor_reject_appointment(
        db,
        appointment_id=appointment_id,
        doctor_user_id=user["sub"],
        reason=request.reason,
    )
    return AppointmentOutcomeResponse(
        appointment_id=appt.appointment_id,
        status=appt.status,
        changed_at=datetime.now().isoformat(),
        message="Appointment rejected successfully.",
    )


@router.post("/{appointment_id}/notes", response_model=AppointmentNoteResponse, status_code=201)
def add_appointment_note(
    appointment_id: UUID = Path(...),
    request: AppointmentNoteRequest,
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> AppointmentNoteResponse:
    note = create_appointment_note(db, appointment_id=appointment_id, doctor_user_id=user["sub"], content=request.content)
    return AppointmentNoteResponse(
        note_id=note.note_id,
        appointment_id=note.appointment_id,
        doctor_id=note.doctor_id,
        content=note.content,
        created_at=note.created_at.isoformat(),
        updated_at=note.updated_at.isoformat(),
    )


@router.get("/{appointment_id}/notes", response_model=List[AppointmentNoteResponse])
def get_appointment_notes(
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> List[AppointmentNoteResponse]:
    notes = list_appointment_notes(db, appointment_id=appointment_id, doctor_user_id=user["sub"])
    return [
        AppointmentNoteResponse(
            note_id=note.note_id,
            appointment_id=note.appointment_id,
            doctor_id=note.doctor_id,
            content=note.content,
            created_at=note.created_at.isoformat(),
            updated_at=note.updated_at.isoformat(),
        )
        for note in notes
    ]


@router.post("/{appointment_id}/prescriptions", response_model=PrescriptionResponse, status_code=201)
def create_appointment_prescription(
    request: PrescriptionRequest,
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> PrescriptionResponse:
    prescription = create_prescription(db, appointment_id=appointment_id, doctor_user_id=user["sub"], request=request)
    return PrescriptionResponse(
        prescription_id=prescription.prescription_id,
        appointment_id=prescription.appointment_id,
        doctor_id=prescription.doctor_id,
        patient_id=prescription.patient_id,
        clinic_id=prescription.clinic_id,
        medications=prescription.medications,
        instructions=prescription.instructions,
        status=prescription.status,
        issued_at=prescription.issued_at.isoformat() if prescription.issued_at else None,
        finalized_at=prescription.finalized_at.isoformat() if prescription.finalized_at else None,
        created_at=prescription.created_at.isoformat(),
        updated_at=prescription.updated_at.isoformat(),
    )


@router.patch("/{appointment_id}/prescriptions/{prescription_id}", response_model=PrescriptionResponse)
def update_appointment_prescription(
    request: PrescriptionRequest,
    appointment_id: UUID = Path(...),
    prescription_id: UUID = Path(...),
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> PrescriptionResponse:
    prescription = update_prescription(
        db,
        appointment_id=appointment_id,
        prescription_id=prescription_id,
        doctor_user_id=user["sub"],
        request=request,
    )
    return PrescriptionResponse(
        prescription_id=prescription.prescription_id,
        appointment_id=prescription.appointment_id,
        doctor_id=prescription.doctor_id,
        patient_id=prescription.patient_id,
        clinic_id=prescription.clinic_id,
        medications=prescription.medications,
        instructions=prescription.instructions,
        status=prescription.status,
        issued_at=prescription.issued_at.isoformat() if prescription.issued_at else None,
        finalized_at=prescription.finalized_at.isoformat() if prescription.finalized_at else None,
        created_at=prescription.created_at.isoformat(),
        updated_at=prescription.updated_at.isoformat(),
    )


@router.post("/{appointment_id}/prescriptions/{prescription_id}/finalize", response_model=PrescriptionResponse)
def finalize_appointment_prescription(
    appointment_id: UUID = Path(...),
    prescription_id: UUID = Path(...),
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> PrescriptionResponse:
    prescription = finalize_prescription(
        db,
        appointment_id=appointment_id,
        prescription_id=prescription_id,
        doctor_user_id=user["sub"],
    )
    return PrescriptionResponse(
        prescription_id=prescription.prescription_id,
        appointment_id=prescription.appointment_id,
        doctor_id=prescription.doctor_id,
        patient_id=prescription.patient_id,
        clinic_id=prescription.clinic_id,
        medications=prescription.medications,
        instructions=prescription.instructions,
        status=prescription.status,
        issued_at=prescription.issued_at.isoformat() if prescription.issued_at else None,
        finalized_at=prescription.finalized_at.isoformat() if prescription.finalized_at else None,
        created_at=prescription.created_at.isoformat(),
        updated_at=prescription.updated_at.isoformat(),
    )


@router.get("/{appointment_id}/prescriptions", response_model=List[PrescriptionResponse])
def get_appointment_prescriptions(
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> List[PrescriptionResponse]:
    prescriptions = list_prescriptions(db, appointment_id=appointment_id, doctor_user_id=user["sub"])
    return [
        PrescriptionResponse(
            prescription_id=prescription.prescription_id,
            appointment_id=prescription.appointment_id,
            doctor_id=prescription.doctor_id,
            patient_id=prescription.patient_id,
            clinic_id=prescription.clinic_id,
            medications=prescription.medications,
            instructions=prescription.instructions,
            status=prescription.status,
            issued_at=prescription.issued_at.isoformat() if prescription.issued_at else None,
            finalized_at=prescription.finalized_at.isoformat() if prescription.finalized_at else None,
            created_at=prescription.created_at.isoformat(),
            updated_at=prescription.updated_at.isoformat(),
        )
        for prescription in prescriptions
    ]


@router.get("/{appointment_id}/patient-summary", response_model=PatientSummaryResponse)
def doctor_patient_summary(
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> PatientSummaryResponse:
    summary = get_patient_summary(db, appointment_id=appointment_id, doctor_user_id=user["sub"])
    return PatientSummaryResponse(**summary)


@router.post("/{appointment_id}/patient-documents", response_model=PatientDocumentResponse, status_code=201)
def upload_patient_document(
    appointment_id: UUID = Path(...),
    request: PatientDocumentRequest,
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> PatientDocumentResponse:
    document = create_patient_document(db, appointment_id=appointment_id, doctor_user_id=user["sub"], request=request)
    return PatientDocumentResponse(
        document_id=document.document_id,
        patient_id=document.patient_id,
        appointment_id=document.appointment_id,
        name=document.name,
        document_type=document.document_type,
        url=document.url,
        description=document.description,
        uploaded_by=document.uploaded_by,
        uploaded_at=document.uploaded_at.isoformat(),
    )


@router.get("/{appointment_id}/patient-documents", response_model=PatientDocumentsResponse)
def doctor_patient_documents(
    appointment_id: UUID = Path(...),
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> PatientDocumentsResponse:
    documents = list_patient_documents(db, appointment_id=appointment_id, doctor_user_id=user["sub"])
    return PatientDocumentsResponse(
        results=[
            PatientDocumentResponse(
                document_id=document.document_id,
                patient_id=document.patient_id,
                appointment_id=document.appointment_id,
                name=document.name,
                document_type=document.document_type,
                url=document.url,
                description=document.description,
                uploaded_by=document.uploaded_by,
                uploaded_at=document.uploaded_at.isoformat(),
            )
            for document in documents
        ],
        total=len(documents),
    )


@router.get("/requests", response_model=AppointmentListPaginatedResponse, status_code=200)
def doctor_pending_requests(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query("pending_doctor", description="Filter requests by appointment status."),
    consultation_type: Optional[str] = Query(None, description="Filter by physical or telemedicine"),
    user: dict = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> AppointmentListPaginatedResponse:
    return fetch_appointment_history(
        db,
        user=user,
        page=page,
        size=size,
        filter_status=status,
        filter_type=consultation_type,
    )
