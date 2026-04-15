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

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'roleenum'
          AND n.nspname = 'auth'
    ) THEN
        CREATE TYPE auth.roleenum AS ENUM ('admin', 'doctor', 'patient', 'staff');
    END IF;

    ALTER TYPE auth.roleenum ADD VALUE IF NOT EXISTS 'admin';
    ALTER TYPE auth.roleenum ADD VALUE IF NOT EXISTS 'doctor';
    ALTER TYPE auth.roleenum ADD VALUE IF NOT EXISTS 'patient';
    ALTER TYPE auth.roleenum ADD VALUE IF NOT EXISTS 'staff';
END
$$;

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
) ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- Shared deterministic seed users (for connected local data)
-- password for all seeded users: admin123
-- ============================================================

INSERT INTO auth.users (id, email, password, role, is_active, is_verified)
VALUES
    ('11111111-1111-4111-8111-111111111111', 'seed.admin@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', 'admin', TRUE, TRUE),
    ('22222222-2222-4222-8222-222222222222', 'dr.anura@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', 'doctor', TRUE, TRUE),
    ('33333333-3333-4333-8333-333333333333', 'dr.nadee@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', 'doctor', TRUE, TRUE),
    ('44444444-4444-4444-8444-444444444444', 'kamal.perera@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', 'patient', TRUE, TRUE),
    ('55555555-5555-4555-8555-555555555555', 'nimali.silva@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', 'patient', TRUE, TRUE),
    ('66666666-6666-4666-8666-666666666666', 'clinic.admin@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', 'staff', TRUE, TRUE),
    ('77777777-7777-4777-8777-777777777777', 'clinic.staff@medstream.lk', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36ZKPPuBPpqA6E2dVCPf2K2', 'staff', TRUE, TRUE)
ON CONFLICT (email) DO UPDATE
SET
    password = EXCLUDED.password,
    role = EXCLUDED.role,
    is_active = EXCLUDED.is_active,
    is_verified = EXCLUDED.is_verified;