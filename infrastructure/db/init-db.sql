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

CREATE TABLE IF NOT EXISTS auth.roles (
    role_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name TEXT      UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth.users (
    user_id        UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    email          TEXT      UNIQUE NOT NULL,
    phone          TEXT      UNIQUE,
    password_hash  TEXT      NOT NULL,
    is_verified    BOOLEAN   NOT NULL DEFAULT TRUE,
    account_status TEXT      NOT NULL DEFAULT 'ACTIVE',
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth.user_roles (
    user_role_id UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID      NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    role_id      INTEGER   NOT NULL REFERENCES auth.roles(role_id) ON DELETE CASCADE,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS auth.auth_sessions (
    session_id    UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID      NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    refresh_token TEXT      UNIQUE NOT NULL,
    expires_at    TIMESTAMP NOT NULL,
    is_revoked    BOOLEAN   NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth.otp_verifications (
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
    ('patient', 'Patient')
ON CONFLICT (role_name) DO NOTHING;

-- Seed default admin (password = "admin123")
INSERT INTO auth.users (email, password_hash, is_verified, account_status)
VALUES (
    'admin@medstream.lk',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2',
    TRUE,
    'ACTIVE'
) ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- Shared deterministic seed users (for connected local data)
-- password for all seeded users: admin123
-- ============================================================

INSERT INTO auth.users (user_id, email, password_hash, is_verified, account_status)
VALUES
    ('11111111-1111-4111-8111-111111111111', 'seed.admin@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', TRUE, 'ACTIVE'),
    ('22222222-2222-4222-8222-222222222222', 'dr.anura@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', TRUE, 'ACTIVE'),
    ('33333333-3333-4333-8333-333333333333', 'dr.nadee@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', TRUE, 'ACTIVE'),
    ('44444444-4444-4444-8444-444444444444', 'kamal.perera@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', TRUE, 'ACTIVE'),
    ('55555555-5555-4555-8555-555555555555', 'nimali.silva@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', TRUE, 'ACTIVE'),
    ('66666666-6666-4666-8666-666666666666', 'clinic.admin@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', TRUE, 'ACTIVE'),
    ('77777777-7777-4777-8777-777777777777', 'clinic.staff@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', TRUE, 'ACTIVE')
ON CONFLICT (email) DO NOTHING;

INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM auth.users u
JOIN auth.roles r ON r.role_name = 'admin'
WHERE u.email = 'admin@medstream.lk'
ON CONFLICT (user_id, role_id) DO NOTHING;

INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM auth.users u
JOIN auth.roles r ON r.role_name = 'admin'
WHERE u.email = 'seed.admin@medstream.lk'
ON CONFLICT (user_id, role_id) DO NOTHING;

INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM auth.users u
JOIN auth.roles r ON r.role_name = 'doctor'
WHERE u.email IN ('dr.anura@medstream.lk', 'dr.nadee@medstream.lk')
ON CONFLICT (user_id, role_id) DO NOTHING;

INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM auth.users u
JOIN auth.roles r ON r.role_name = 'patient'
WHERE u.email IN ('kamal.perera@medstream.lk', 'nimali.silva@medstream.lk')
ON CONFLICT (user_id, role_id) DO NOTHING;

INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM auth.users u
JOIN auth.roles r ON r.role_name = 'clinic_admin'
WHERE u.email = 'clinic.admin@medstream.lk'
ON CONFLICT (user_id, role_id) DO NOTHING;

INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id
FROM auth.users u
JOIN auth.roles r ON r.role_name = 'clinic_staff'
WHERE u.email = 'clinic.staff@medstream.lk'
ON CONFLICT (user_id, role_id) DO NOTHING;
