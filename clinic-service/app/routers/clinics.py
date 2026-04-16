from typing import List, Sequence

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ClinicResponse, CreateClinicRequest
from app.services.clinic import create_clinic, list_clinics

router = APIRouter(tags=["Clinics"])


@router.post("/", response_model=ClinicResponse, status_code=status.HTTP_201_CREATED)
def create_clinic_endpoint(
    payload: CreateClinicRequest,
    db: Session = Depends(get_db),
) -> ClinicResponse:
    clinic = create_clinic(db=db, payload=payload)
    return ClinicResponse.model_validate(clinic)


@router.get("/", response_model=List[ClinicResponse])
def get_clinics_endpoint(db: Session = Depends(get_db)) -> Sequence[ClinicResponse]:
    return [ClinicResponse.model_validate(clinic) for clinic in list_clinics(db=db)]
