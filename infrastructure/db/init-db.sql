-- ============================================================
-- MedStream Database Initialization
-- ============================================================

-- Create databases
CREATE DATABASE medstream_auth;
CREATE DATABASE medstream_clinic;
CREATE DATABASE medstream_payments;

-- Create shared app user
CREATE USER dev_user WITH PASSWORD 'dev_password';

-- Grant privileges on each database
GRANT ALL PRIVILEGES ON DATABASE medstream_auth     TO dev_user;
GRANT ALL PRIVILEGES ON DATABASE medstream_clinic   TO dev_user;
GRANT ALL PRIVILEGES ON DATABASE medstream_payments TO dev_user;

-- ============================================================
-- Auth database setup
-- ============================================================
\connect medstream_auth

CREATE SCHEMA IF NOT EXISTS auth;
GRANT ALL ON SCHEMA auth TO dev_user;

CREATE TYPE auth.roleenum AS ENUM ('admin', 'doctor', 'patient');

CREATE TABLE IF NOT EXISTS auth.users (
    id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT          UNIQUE NOT NULL,
    password      TEXT          NOT NULL,
    role          auth.roleenum NOT NULL DEFAULT 'patient',
    is_active     BOOLEAN       NOT NULL DEFAULT TRUE,
    is_verified   BOOLEAN       NOT NULL DEFAULT TRUE,
    refresh_token TEXT,
    created_at    TIMESTAMP     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth.token_blacklist (
    id         UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    token      TEXT      UNIQUE NOT NULL,
    revoked_at TIMESTAMP NOT NULL DEFAULT NOW()
);

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA auth TO dev_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA auth TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT ALL ON TABLES    TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT ALL ON SEQUENCES TO dev_user;

-- Seed default admin (password = "admin123")
INSERT INTO auth.users (email, password, role, is_verified)
VALUES (
    'admin@medstream.lk',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2',
    'admin',
    TRUE
) ON CONFLICT DO NOTHING;

-- ============================================================
-- Clinic database setup
-- ============================================================
\connect medstream_clinic

CREATE SCHEMA IF NOT EXISTS clinic;
GRANT ALL ON SCHEMA clinic TO dev_user;

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA clinic TO dev_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA clinic TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA clinic GRANT ALL ON TABLES    TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA clinic GRANT ALL ON SEQUENCES TO dev_user;

-- ============================================================
-- Payments database setup
-- ============================================================
\connect medstream_payments

CREATE SCHEMA IF NOT EXISTS payments;
GRANT ALL ON SCHEMA payments TO dev_user;

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA payments TO dev_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA payments TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA payments GRANT ALL ON TABLES    TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA payments GRANT ALL ON SEQUENCES TO dev_user;