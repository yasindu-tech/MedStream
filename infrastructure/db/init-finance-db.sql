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

-- Set Search Path
SET search_path TO finance, public;

-- ENUM Types
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE t.typname = 'payment_status' AND n.nspname = 'finance') THEN
        CREATE TYPE finance.payment_status AS ENUM ('pending', 'processing', 'paid', 'failed', 'refunded', 'expired');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE t.typname = 'split_type' AND n.nspname = 'finance') THEN
        CREATE TYPE finance.split_type AS ENUM ('platform', 'clinic', 'doctor');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE t.typname = 'split_status' AND n.nspname = 'finance') THEN
        CREATE TYPE finance.split_status AS ENUM ('pending', 'settled', 'reversed');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE t.typname = 'refund_status' AND n.nspname = 'finance') THEN
        CREATE TYPE finance.refund_status AS ENUM ('pending', 'approved', 'rejected', 'processed', 'failed');
    END IF;
END
$$;

-- Grant usage on types to dev_user
GRANT USAGE ON TYPE finance.payment_status TO dev_user;
GRANT USAGE ON TYPE finance.split_type TO dev_user;
GRANT USAGE ON TYPE finance.split_status TO dev_user;
GRANT USAGE ON TYPE finance.refund_status TO dev_user;

-- PAYMENTS Table
CREATE TABLE IF NOT EXISTS finance.payments (
    payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id UUID NOT NULL UNIQUE,
    patient_id UUID NOT NULL,
    doctor_id UUID NOT NULL,
    clinic_id UUID,
    amount NUMERIC(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
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
CREATE TABLE IF NOT EXISTS finance.payment_splits (
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
CREATE TABLE IF NOT EXISTS finance.refunds (
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
