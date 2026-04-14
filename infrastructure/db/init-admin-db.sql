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

-- ============================================================
-- Core entities from AdminDB ERD
-- ============================================================

CREATE TABLE IF NOT EXISTS admin.clinics (
    clinic_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_name varchar(255) NOT NULL,
    registration_no varchar(120),
    address text,
    phone varchar(30),
    email varchar(255),
    status varchar(30) NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_clinics_registration_no
    ON admin.clinics (registration_no)
    WHERE registration_no IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_clinics_email
    ON admin.clinics (email)
    WHERE email IS NOT NULL;

CREATE TABLE IF NOT EXISTS admin.clinic_admins (
    clinic_admin_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL,
    user_id uuid,
    status varchar(30) NOT NULL DEFAULT 'active',
    assigned_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_clinic_admins_clinic
        FOREIGN KEY (clinic_id) REFERENCES admin.clinics(clinic_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin.clinic_staff (
    staff_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL,
    user_id uuid,
    staff_role varchar(100),
    status varchar(30) NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_clinic_staff_clinic
        FOREIGN KEY (clinic_id) REFERENCES admin.clinics(clinic_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin.doctors (
    doctor_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid,
    full_name varchar(255) NOT NULL,
    medical_registration_no varchar(120),
    specialization varchar(120),
    consultation_mode varchar(40),
    verification_status varchar(30) NOT NULL DEFAULT 'pending',
    status varchar(30) NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_doctors_medical_registration_no
    ON admin.doctors (medical_registration_no)
    WHERE medical_registration_no IS NOT NULL;

CREATE TABLE IF NOT EXISTS admin.doctor_clinic_assignments (
    assignment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id uuid NOT NULL,
    clinic_id uuid NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'active',
    assigned_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_assign_doctor
        FOREIGN KEY (doctor_id) REFERENCES admin.doctors(doctor_id) ON DELETE CASCADE,
    CONSTRAINT fk_assign_clinic
        FOREIGN KEY (clinic_id) REFERENCES admin.clinics(clinic_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin.doctor_availability (
    availability_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id uuid NOT NULL,
    clinic_id uuid NOT NULL,
    day_of_week varchar(20) NOT NULL,
    start_time varchar(20) NOT NULL,
    end_time varchar(20) NOT NULL,
    slot_duration integer NOT NULL,
    consultation_type varchar(40),
    status varchar(30) NOT NULL DEFAULT 'active',
    CONSTRAINT fk_doctor_availability_doctor
        FOREIGN KEY (doctor_id) REFERENCES admin.doctors(doctor_id) ON DELETE CASCADE,
    CONSTRAINT fk_doctor_availability_clinic
        FOREIGN KEY (clinic_id) REFERENCES admin.clinics(clinic_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin.clinic_payment_accounts (
    payment_account_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL,
    provider_name varchar(120) NOT NULL,
    account_reference varchar(200),
    verification_status varchar(30) NOT NULL DEFAULT 'pending',
    connected_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_clinic_payment_account_clinic
        FOREIGN KEY (clinic_id) REFERENCES admin.clinics(clinic_id) ON DELETE CASCADE,
    CONSTRAINT uq_clinic_payment_account UNIQUE (clinic_id)
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA admin TO dev_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA admin TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA admin GRANT ALL ON TABLES TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA admin GRANT ALL ON SEQUENCES TO dev_user;
