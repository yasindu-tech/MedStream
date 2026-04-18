from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from app.models.payment import PaymentStatus, SplitType, RefundStatus, SplitStatus

class PaymentBase(BaseModel):
    appointment_id: UUID
    patient_id: UUID
    doctor_id: UUID
    clinic_id: Optional[UUID] = None
    amount: Decimal
    currency: str = "LKR"
    doctor_amount: Optional[Decimal] = None
    clinic_amount: Optional[Decimal] = None
    system_amount: Optional[Decimal] = None

class PaymentCreate(PaymentBase):
    pass

class PaymentSplitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    split_id: UUID
    split_type: SplitType
    beneficiary_id: UUID
    percentage: Decimal
    amount: Decimal
    status: SplitStatus
    created_at: datetime

class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    refund_id: UUID
    refund_amount: Decimal
    reason: Optional[str] = None
    status: RefundStatus
    requested_by: Optional[UUID] = None
    reviewed_by: Optional[UUID] = None
    refunded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class PaymentResponse(PaymentBase):
    model_config = ConfigDict(from_attributes=True)
    
    payment_id: UUID
    status: PaymentStatus
    transaction_reference: Optional[str] = None
    retry_count: int
    max_retries: int
    expires_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    splits: List[PaymentSplitResponse] = []
    refunds: List[RefundResponse] = []

class PaymentInitiateResponse(BaseModel):
    payment_id: UUID
    gateway_url: str
    transaction_reference: str
    expires_at: Optional[datetime]

class MockPayRequest(BaseModel):
    payment_id: UUID
    action: str = "success" # "success" or "fail"

class RefundCreate(BaseModel):
    reason: str

class MyEarningsSummary(BaseModel):
    total_earned: Decimal
    total_pending: Decimal
    total_reversed: Decimal
    splits: List[PaymentSplitResponse]

class ClinicSummary(BaseModel):
    total_revenue: Decimal
    total_refunded: Decimal
    total_failed: Decimal
    clinic_share_total: Decimal
    total_bookings: int
    period_start: Optional[datetime]
    period_end: Optional[datetime]

class PlatformSummary(BaseModel):
    total_revenue: Decimal
    platform_earnings: Decimal
    distinct_patients: int
    total_payments: int
    total_refunded: Decimal
    total_failed: Decimal
    total_settled: Decimal
    total_processing: Decimal
    refund_count: int

class ReceiptResponse(BaseModel):
    receipt_id: UUID
    payment_id: UUID
    appointment_id: UUID
    patient_id: UUID
    doctor_id: UUID
    clinic_id: Optional[UUID]
    amount: Decimal
    currency: str
    transaction_reference: Optional[str]
    paid_at: Optional[datetime]
    generated_at: datetime
    splits: List[PaymentSplitResponse]
