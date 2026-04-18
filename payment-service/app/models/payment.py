from sqlalchemy import Column, String, Numeric, Enum, Integer, DateTime, ForeignKey, text, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base
import enum

class PaymentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"
    expired = "expired"

class SplitType(str, enum.Enum):
    platform = "platform"
    clinic = "clinic"
    doctor = "doctor"

class RefundStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    processed = "processed"
    failed = "failed"

class SplitStatus(str, enum.Enum):
    pending = "pending"
    settled = "settled"
    reversed = "reversed"

class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = {"schema": "finance"}

    payment_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    appointment_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    patient_id = Column(UUID(as_uuid=True), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), nullable=False)
    clinic_id = Column(UUID(as_uuid=True), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="LKR")
    doctor_amount = Column(Numeric(10, 2), nullable=True)
    clinic_amount = Column(Numeric(10, 2), nullable=True)
    system_amount = Column(Numeric(10, 2), nullable=True)
    provider_name = Column(String(50), default="stripe")
    transaction_reference = Column(String(255))
    status = Column(Enum(PaymentStatus, create_type=False, name="payment_status", schema="finance"), server_default="pending")
    failure_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    expires_at = Column(DateTime(timezone=True))
    paid_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    splits = relationship("PaymentSplit", back_populates="payment", cascade="all, delete-orphan")
    refunds = relationship("Refund", back_populates="payment", cascade="all, delete-orphan")

class PaymentSplit(Base):
    __tablename__ = "payment_splits"
    __table_args__ = {"schema": "finance"}

    split_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    payment_id = Column(UUID(as_uuid=True), ForeignKey("finance.payments.payment_id"), nullable=False)
    split_type = Column(Enum(SplitType, create_type=False, name="split_type", schema="finance"), nullable=False)
    beneficiary_id = Column(UUID(as_uuid=True), nullable=False)
    percentage = Column(Numeric(5, 2), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(Enum(SplitStatus, create_type=False, name="split_status", schema="finance"), server_default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payment = relationship("Payment", back_populates="splits")

class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = {"schema": "finance"}

    refund_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    payment_id = Column(UUID(as_uuid=True), ForeignKey("finance.payments.payment_id"), nullable=False)
    refund_amount = Column(Numeric(10, 2), nullable=False)
    reason = Column(Text)
    status = Column(Enum(RefundStatus, create_type=False, name="refund_status", schema="finance"), server_default="pending")
    requested_by = Column(UUID(as_uuid=True))
    reviewed_by = Column(UUID(as_uuid=True))
    refunded_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    payment = relationship("Payment", back_populates="refunds")
