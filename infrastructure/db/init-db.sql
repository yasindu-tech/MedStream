-- ============================================================
-- AuthDB Initialization (medstream_auth)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dev_user') THEN
        CREATE ROLE dev_user LOGIN PASSWORD 'dev_password';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE medstream_auth TO dev_user;

CREATE SCHEMA IF NOT EXISTS auth;
GRANT ALL ON SCHEMA auth TO dev_user;

CREATE TABLE auth.roles (
    role_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name TEXT      UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE auth.users (
    user_id            UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name          TEXT,
    email              TEXT      UNIQUE NOT NULL,
    phone              TEXT      UNIQUE,
    password_hash      TEXT      NOT NULL,
    is_verified        BOOLEAN   NOT NULL DEFAULT TRUE,
    account_status     TEXT      NOT NULL DEFAULT 'ACTIVE',
    suspension_reason  TEXT,
    created_at         TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE auth.user_roles (
    user_role_id UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID      NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    role_id      INTEGER   NOT NULL REFERENCES auth.roles(role_id) ON DELETE CASCADE,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, role_id)
);

CREATE TABLE auth.auth_sessions (
    session_id    UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID      NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    refresh_token TEXT      UNIQUE NOT NULL,
    expires_at    TIMESTAMP NOT NULL,
    is_revoked    BOOLEAN   NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE auth.otp_verifications (
    otp_id      UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID      NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    otp_code    TEXT      NOT NULL,
    purpose     TEXT      NOT NULL,
    expires_at  TIMESTAMP NOT NULL,
    is_used     BOOLEAN   NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA auth TO dev_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA auth TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT ALL ON TABLES    TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT ALL ON SEQUENCES TO dev_user;

-- Seed default roles
INSERT INTO auth.roles (role_name, description)
VALUES
    ('admin', 'System administrator'),
    ('clinic_admin', 'Clinic administrator'),
    ('clinic_staff', 'Clinic staff'),
    ('doctor', 'Doctor'),
    ('patient', 'Patient');

-- Seed default users (password = "admin123")
-- password_hash for "admin123" is $2b$12$UYjCKV1OyD.dFWjyLD2xcOavNGgtXlvQLZf7LD.P6ouygJrVnLGXO
INSERT INTO auth.users (user_id, full_name, email, password_hash, is_verified, account_status)
VALUES
    ('11111111-1111-4111-8111-111111111111', 'System Admin', 'admin@medstream.lk', '$2b$12$UYjCKV1OyD.dFWjyLD2xcOavNGgtXlvQLZf7LD.P6ouygJrVnLGXO', TRUE, 'ACTIVE'),
    ('22222222-2222-4222-8222-222222222222', 'Dr. Anura Bandara', 'dr.anura@medstream.lk', '$2b$12$UYjCKV1OyD.dFWjyLD2xcOavNGgtXlvQLZf7LD.P6ouygJrVnLGXO', TRUE, 'ACTIVE'),
    ('33333333-3333-4333-8333-333333333333', 'Dr. Nadeesha Perera', 'dr.nadee@medstream.lk', '$2b$12$UYjCKV1OyD.dFWjyLD2xcOavNGgtXlvQLZf7LD.P6ouygJrVnLGXO', TRUE, 'ACTIVE'),
    ('44444444-4444-4444-8444-444444444444', 'Kamal Perera', 'kamal.perera@medstream.lk', '$2b$12$UYjCKV1OyD.dFWjyLD2xcOavNGgtXlvQLZf7LD.P6ouygJrVnLGXO', TRUE, 'ACTIVE'),
    ('55555555-5555-4555-8555-555555555555', 'Nimali Silva', 'nimali.silva@medstream.lk', '$2b$12$UYjCKV1OyD.dFWjyLD2xcOavNGgtXlvQLZf7LD.P6ouygJrVnLGXO', TRUE, 'ACTIVE'),
    ('66666666-6666-4666-8666-666666666666', 'Clinic Admin', 'clinic.admin@medstream.lk', '$2b$12$UYjCKV1OyD.dFWjyLD2xcOavNGgtXlvQLZf7LD.P6ouygJrVnLGXO', TRUE, 'ACTIVE'),
    ('77777777-7777-4777-8777-777777777777', 'Clinic Staff', 'clinic.staff@medstream.lk', '$2b$12$UYjCKV1OyD.dFWjyLD2xcOavNGgtXlvQLZf7LD.P6ouygJrVnLGXO', TRUE, 'ACTIVE');

INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id FROM auth.users u, auth.roles r WHERE u.email = 'admin@medstream.lk' AND r.role_name = 'admin';

INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id FROM auth.users u, auth.roles r WHERE u.email IN ('dr.anura@medstream.lk', 'dr.nadee@medstream.lk') AND r.role_name = 'doctor';

INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id FROM auth.users u, auth.roles r WHERE u.email IN ('kamal.perera@medstream.lk', 'nimali.silva@medstream.lk') AND r.role_name = 'patient';

INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id FROM auth.users u, auth.roles r WHERE u.email = 'clinic.admin@medstream.lk' AND r.role_name = 'clinic_admin';

INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id FROM auth.users u, auth.roles r WHERE u.email = 'clinic.staff@medstream.lk' AND r.role_name = 'clinic_staff';
