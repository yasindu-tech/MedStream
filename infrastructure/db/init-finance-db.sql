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

CREATE TABLE IF NOT EXISTS finance.payments (
    payment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id uuid,
    patient_id uuid,
    amount numeric(12,2) NOT NULL,
    currency varchar(10) NOT NULL DEFAULT 'LKR',
    status varchar(30) NOT NULL DEFAULT 'pending',
    provider_ref varchar(120),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS finance.payment_splits (
    split_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id uuid NOT NULL,
    recipient_type varchar(50) NOT NULL,
    recipient_id uuid,
    amount numeric(12,2) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_payment_splits_payment FOREIGN KEY (payment_id) REFERENCES finance.payments(payment_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS finance.refunds (
    refund_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id uuid NOT NULL,
    amount numeric(12,2) NOT NULL,
    reason text,
    status varchar(30) NOT NULL DEFAULT 'requested',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_refunds_payment FOREIGN KEY (payment_id) REFERENCES finance.payments(payment_id) ON DELETE CASCADE
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA finance TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA finance GRANT ALL ON TABLES TO dev_user;
