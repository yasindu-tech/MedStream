from sqlalchemy import Column, String, Numeric, Enum, Integer, DateTime, ForeignKey, text, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base
import enum

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    EXPIRED = "expired"

class SplitType(str, enum.Enum):
    PLATFORM = "platform"
    CLINIC = "clinic"
    DOCTOR = "doctor"

class RefundStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSED = "processed"
    FAILED = "failed"

class SplitStatus(str, enum.Enum):
    PENDING = "pending"
    SETTLED = "settled"
    REVERSED = "reversed"

class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = {"schema": "finance"}

    payment_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    appointment_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    patient_id = Column(UUID(as_uuid=True), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), nullable=False)
    clinic_id = Column(UUID(as_uuid=True), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    provider_name = Column(String(50), default="stripe")
    transaction_reference = Column(String(255))
    status = Column(Enum(PaymentStatus, create_type=True, name="payment_status", schema="finance"), server_default="pending")
    failure_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    expires_at = Column(DateTime(timezone=True))
    paid_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PaymentSplit(Base):
    __tablename__ = "payment_splits"
    __table_args__ = {"schema": "finance"}

    split_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    payment_id = Column(UUID(as_uuid=True), ForeignKey("finance.payments.payment_id"), nullable=False)
    split_type = Column(Enum(SplitType, create_type=True, name="split_type", schema="finance"), nullable=False)
    beneficiary_id = Column(UUID(as_uuid=True), nullable=False)
    percentage = Column(Numeric(5, 2), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(Enum(SplitStatus, create_type=True, name="split_status", schema="finance"), server_default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = {"schema": "finance"}

    refund_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    payment_id = Column(UUID(as_uuid=True), ForeignKey("finance.payments.payment_id"), nullable=False)
    refund_amount = Column(Numeric(10, 2), nullable=False)
    reason = Column(Text)
    status = Column(Enum(RefundStatus, create_type=True, name="refund_status", schema="finance"), server_default="pending")
    requested_by = Column(UUID(as_uuid=True))
    reviewed_by = Column(UUID(as_uuid=True))
    refunded_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
