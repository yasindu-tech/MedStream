-- ============================================================
-- FinanceDB Initialization (medstream_finance)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dev_user') THEN
        CREATE ROLE dev_user LOGIN PASSWORD 'dev_password';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE medstream_finance TO dev_user;

CREATE SCHEMA IF NOT EXISTS finance;
GRANT ALL ON SCHEMA finance TO dev_user;

SET search_path TO finance, public;

-- ENUM Types
CREATE TYPE finance.payment_status AS ENUM ('pending', 'processing', 'paid', 'failed', 'refunded', 'expired');
CREATE TYPE finance.split_type AS ENUM ('platform', 'clinic', 'doctor');
CREATE TYPE finance.split_status AS ENUM ('pending', 'settled', 'reversed');
CREATE TYPE finance.refund_status AS ENUM ('pending', 'approved', 'rejected', 'processed', 'failed');

GRANT USAGE ON TYPE finance.payment_status TO dev_user;
GRANT USAGE ON TYPE finance.split_type TO dev_user;
GRANT USAGE ON TYPE finance.split_status TO dev_user;
GRANT USAGE ON TYPE finance.refund_status TO dev_user;

-- PAYMENTS Table
CREATE TABLE finance.payments (
    payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id UUID NOT NULL UNIQUE,
    patient_id UUID NOT NULL,
    doctor_id UUID NOT NULL,
    clinic_id UUID,
    amount NUMERIC(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'LKR',
    doctor_amount NUMERIC(10, 2),
    clinic_amount NUMERIC(10, 2),
    system_amount NUMERIC(10, 2),
    provider_name VARCHAR(50) DEFAULT 'stripe',
    transaction_reference VARCHAR(255),
    status finance.payment_status DEFAULT 'pending',
    failure_reason TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    expires_at TIMESTAMP WITH TIME ZONE,
    paid_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- PAYMENT_SPLITS Table
CREATE TABLE finance.payment_splits (
    split_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID NOT NULL REFERENCES finance.payments(payment_id) ON DELETE CASCADE,
    split_type finance.split_type NOT NULL,
    beneficiary_id UUID NOT NULL,
    percentage NUMERIC(5, 2) NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    status finance.split_status DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- REFUNDS Table
CREATE TABLE finance.refunds (
    refund_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID NOT NULL REFERENCES finance.payments(payment_id) ON DELETE CASCADE,
    refund_amount NUMERIC(10, 2) NOT NULL,
    reason TEXT,
    status finance.refund_status DEFAULT 'pending',
    requested_by UUID,
    reviewed_by UUID,
    refunded_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA finance TO dev_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA finance TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA finance GRANT ALL ON TABLES TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA finance GRANT ALL ON SEQUENCES TO dev_user;
