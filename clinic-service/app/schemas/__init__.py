from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, constr


class CreateClinicRequest(BaseModel):
    clinic_name: str = Field(..., min_length=3, description="The clinic's display name")
    registration_no: str = Field(..., min_length=3, description="Unique registration identifier")
    address: str = Field(..., min_length=10, description="Physical address of the clinic")
    phone: str = Field(..., min_length=7, max_length=30, description="Contact phone number")
    email: EmailStr = Field(..., description="Contact email address")


class ClinicResponse(BaseModel):
    clinic_id: UUID
    clinic_name: str
    registration_no: str | None
    address: str | None
    phone: str | None
    email: EmailStr | None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateClinicStatusRequest(BaseModel):
    status: Literal["active", "inactive"]
    reason: str | None = Field(None, description="Optional reason for the status change")


class ClinicActionResponse(BaseModel):
    clinic_id: UUID
    status: str
    message: str

    class Config:
        from_attributes = True


PhoneNumber = constr(
    strip_whitespace=True,
    min_length=7,
    max_length=30,
    pattern=r"^[0-9+()\-\s]+$",
)


class CreateClinicStaffRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=3, description="Full name of the clinic staff member")
    phone: PhoneNumber | None = Field(None, description="Contact phone number for the staff member")
    role: str = Field(..., min_length=3, description="Role within the clinic, e.g. receptionist, nurse")


class UpdateClinicStaffRequest(BaseModel):
    name: str | None = Field(None, min_length=3, description="Updated staff full name")
    phone: PhoneNumber | None = Field(None, description="Updated contact phone number")
    role: str | None = Field(None, min_length=3, description="Updated clinic staff role")


class ClinicStaffResponse(BaseModel):
    staff_id: UUID
    clinic_id: UUID
    user_id: UUID | None
    staff_email: EmailStr | None
    staff_name: str | None
    staff_phone: str | None
    staff_role: str | None
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    updated_by: str | None = None

    class Config:
        from_attributes = True


class CreateClinicStaffResponse(BaseModel):
    staff: ClinicStaffResponse
    temporary_password: str

    class Config:
        from_attributes = True


class AvailableDoctorResponse(BaseModel):
    doctor_id: UUID
    full_name: str
    medical_registration_no: str | None = None
    specialization: str | None = None
    consultation_mode: str | None = None
    consultation_fee: float | None = None
    verification_status: str
    status: str

    class Config:
        from_attributes = True


class DoctorAssignmentRequest(BaseModel):
    doctor_id: UUID


class ClinicDoctorResponse(BaseModel):
    assignment_id: UUID
    doctor_id: UUID
    clinic_id: UUID
    full_name: str
    medical_registration_no: str | None = None
    specialization: str | None = None
    consultation_mode: str | None = None
    consultation_fee: float | None = None
    verification_status: str
    doctor_status: str
    assignment_status: str

    class Config:
        from_attributes = True


class ClinicDashboardResponse(BaseModel):
    clinic_id: UUID
    total_appointments: int
    active_doctors: int
    completed_consultations: int
    cancellations: int
    payment_summary: ClinicFinancialSummaryResponse
    warnings: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ClinicFinancialSummaryResponse(BaseModel):
    total_revenue: Decimal
    total_refunded: Decimal
    total_failed: Decimal
    clinic_share_total: Decimal
    period_start: datetime | None = None
    period_end: datetime | None = None

    class Config:
        from_attributes = True


class PaymentSummaryResponse(BaseModel):
    total_revenue: Decimal
    total_refunded: Decimal
    total_failed: Decimal
    total_pending: Decimal
    platform_commission_total: Decimal
    payment_count: int
    refund_count: int

    class Config:
        from_attributes = True


class PlatformDashboardResponse(BaseModel):
    total_clinics: int
    active_doctors: int
    active_patients: int
    daily_bookings: int
    payment_summary: PaymentSummaryResponse
    warnings: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ClinicAppointmentListItemResponse(BaseModel):
    appointment_id: UUID
    doctor_id: UUID
    doctor_name: str | None = None
    clinic_id: UUID
    clinic_name: str | None = None
    patient_id: UUID
    patient_name: str
    date: date
    start_time: str
    end_time: str
    status: str
    payment_status: str
    consultation_type: str

    class Config:
        from_attributes = True


class ClinicAppointmentListPaginatedResponse(BaseModel):
    items: list[ClinicAppointmentListItemResponse]
    total: int
    page: int
    size: int
    has_more: bool

    class Config:
        from_attributes = True
