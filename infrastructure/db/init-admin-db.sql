-- ============================================================
-- AdminDB Initialization (medstream_admin)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dev_user') THEN
        CREATE ROLE dev_user LOGIN PASSWORD 'dev_password';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE medstream_admin TO dev_user;

CREATE SCHEMA IF NOT EXISTS admin;
GRANT ALL ON SCHEMA admin TO dev_user;

-- Core admin-side entities can expand over time
CREATE TABLE IF NOT EXISTS admin.clinics (
    clinic_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_name varchar(255) NOT NULL,
    contact_phone varchar(30),
    address text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admin.doctors (
    doctor_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid,
    full_name varchar(255) NOT NULL,
    specialization varchar(120),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admin.doctor_clinic_assignments (
    assignment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id uuid NOT NULL,
    clinic_id uuid NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_assign_doctor FOREIGN KEY (doctor_id) REFERENCES admin.doctors(doctor_id) ON DELETE CASCADE,
    CONSTRAINT fk_assign_clinic FOREIGN KEY (clinic_id) REFERENCES admin.clinics(clinic_id) ON DELETE CASCADE
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA admin TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA admin GRANT ALL ON TABLES TO dev_user;
