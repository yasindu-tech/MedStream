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
-- Tables
-- ============================================================

CREATE TABLE IF NOT EXISTS admin.clinics (
    clinic_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_name      varchar(255) NOT NULL,
    registration_no  varchar(120),
    address          text,
    phone            varchar(30),
    email            varchar(255),
    status           varchar(30) NOT NULL DEFAULT 'active',
    created_at       timestamptz NOT NULL DEFAULT now()
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
    staff_email varchar(255),
    staff_name varchar(255),
    staff_phone varchar(30),
    staff_role varchar(100),
    status varchar(30) NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz,
    updated_by varchar(100),
    CONSTRAINT fk_clinic_staff_clinic
        FOREIGN KEY (clinic_id) REFERENCES admin.clinics(clinic_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin.clinic_staff_history (
    history_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    staff_id uuid NOT NULL,
    clinic_id uuid NOT NULL,
    user_id uuid,
    staff_email varchar(255),
    staff_name varchar(255),
    staff_phone varchar(30),
    staff_role varchar(100),
    status varchar(30) NOT NULL,
    action varchar(50) NOT NULL,
    changed_by varchar(100),
    changed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admin.doctor_assignment_history (
    history_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id uuid NOT NULL,
    clinic_id uuid NOT NULL,
    action varchar(50) NOT NULL,
    changed_by varchar(100),
    reason text,
    changed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admin.clinic_status_history (
    history_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL,
    old_status varchar(30),
    new_status varchar(30) NOT NULL,
    changed_by varchar(100),
    reason text,
    changed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admin.doctors (
    doctor_id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                  uuid,
    full_name                varchar(255) NOT NULL,
    medical_registration_no  varchar(120),
    specialization           varchar(120),
    consultation_mode        varchar(40),
    verification_status      varchar(30) NOT NULL DEFAULT 'verified',
    status                   varchar(30) NOT NULL DEFAULT 'active',
    verification_documents   jsonb,
    verification_rejection_reason text,
    suspension_reason        text,
    bio                      text,
    experience_years         int,
    qualifications           text,
    profile_image_url        text,
    consultation_fee         numeric(10,2),
    created_at               timestamptz NOT NULL DEFAULT now()
);

-- Ensure new profile columns exist on databases created before AS-02
ALTER TABLE admin.doctors ADD COLUMN IF NOT EXISTS bio                 text;
ALTER TABLE admin.doctors ADD COLUMN IF NOT EXISTS experience_years    int;
ALTER TABLE admin.doctors ADD COLUMN IF NOT EXISTS qualifications      text;
ALTER TABLE admin.doctors ADD COLUMN IF NOT EXISTS profile_image_url   text;
ALTER TABLE admin.doctors ADD COLUMN IF NOT EXISTS consultation_fee    numeric(10,2);
ALTER TABLE admin.doctors ADD COLUMN IF NOT EXISTS specializations      jsonb;
ALTER TABLE admin.doctors ADD COLUMN IF NOT EXISTS primary_specialization varchar(120);
ALTER TABLE admin.doctors ADD COLUMN IF NOT EXISTS verification_documents jsonb;
ALTER TABLE admin.doctors ADD COLUMN IF NOT EXISTS verification_rejection_reason text;
ALTER TABLE admin.doctors ADD COLUMN IF NOT EXISTS suspension_reason    text;

CREATE UNIQUE INDEX IF NOT EXISTS uq_doctors_medical_registration_no
    ON admin.doctors (medical_registration_no)
    WHERE medical_registration_no IS NOT NULL;

CREATE TABLE IF NOT EXISTS admin.doctor_profile_history (
    history_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id    uuid NOT NULL,
    field_name   varchar(100) NOT NULL,
    old_value    text,
    new_value    text,
    changed_by   varchar(100),
    reason       text,
    changed_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_doctor_profile_history_doctor
        FOREIGN KEY (doctor_id) REFERENCES admin.doctors(doctor_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin.doctor_clinic_assignments (
    assignment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id     uuid NOT NULL,
    clinic_id     uuid NOT NULL,
    status        varchar(30) NOT NULL DEFAULT 'active',
    assigned_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_assign_doctor FOREIGN KEY (doctor_id) REFERENCES admin.doctors(doctor_id) ON DELETE CASCADE,
    CONSTRAINT fk_assign_clinic FOREIGN KEY (clinic_id) REFERENCES admin.clinics(clinic_id) ON DELETE CASCADE,
    CONSTRAINT uq_assign UNIQUE (doctor_id, clinic_id)
);

CREATE TABLE IF NOT EXISTS admin.doctor_availability (
    availability_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id         uuid NOT NULL,
    clinic_id         uuid NOT NULL,
    day_of_week       varchar(20) NOT NULL,
    start_time        varchar(10) NOT NULL,
    end_time          varchar(10) NOT NULL,
    slot_duration     int NOT NULL DEFAULT 30,
    consultation_type varchar(40),
    status            varchar(30) NOT NULL DEFAULT 'active',
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_avail_doctor FOREIGN KEY (doctor_id) REFERENCES admin.doctors(doctor_id) ON DELETE CASCADE,
    CONSTRAINT fk_avail_clinic FOREIGN KEY (clinic_id) REFERENCES admin.clinics(clinic_id) ON DELETE CASCADE
);

-- Ensure newer scheduling columns exist on databases created before one-time date support
ALTER TABLE admin.doctor_availability ADD COLUMN IF NOT EXISTS date date;
ALTER TABLE admin.doctor_availability ALTER COLUMN day_of_week DROP NOT NULL;

CREATE TABLE IF NOT EXISTS admin.doctor_availability_history (
    history_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    availability_id  uuid NOT NULL,
    doctor_id        uuid NOT NULL,
    action           varchar(50) NOT NULL,
    old_value        jsonb,
    new_value        jsonb,
    changed_by       varchar(100),
    changed_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_doctor_availability_history_availability
        FOREIGN KEY (availability_id) REFERENCES admin.doctor_availability(availability_id) ON DELETE CASCADE,
    CONSTRAINT fk_doctor_availability_history_doctor
        FOREIGN KEY (doctor_id) REFERENCES admin.doctors(doctor_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin.doctor_leave (
    leave_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id       uuid NOT NULL,
    clinic_id       uuid,
    start_datetime  timestamptz NOT NULL,
    end_datetime    timestamptz NOT NULL,
    reason          text,
    status          varchar(30) NOT NULL DEFAULT 'active',
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_leave_doctor FOREIGN KEY (doctor_id) REFERENCES admin.doctors(doctor_id) ON DELETE CASCADE,
    CONSTRAINT fk_leave_clinic FOREIGN KEY (clinic_id) REFERENCES admin.clinics(clinic_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_doctor_availability_slot
    ON admin.doctor_availability (doctor_id, clinic_id, day_of_week, start_time, consultation_type);

CREATE TABLE IF NOT EXISTS admin.clinic_payment_accounts (
    payment_account_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id           uuid NOT NULL,
    provider_name       varchar(120),
    account_reference   varchar(255),
    verification_status varchar(30) NOT NULL DEFAULT 'pending',
    connected_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_payment_account_clinic
        FOREIGN KEY (clinic_id) REFERENCES admin.clinics(clinic_id) ON DELETE CASCADE
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA admin TO dev_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA admin TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA admin GRANT ALL ON TABLES TO dev_user;

-- ============================================================
-- Seed Data
-- ============================================================

INSERT INTO admin.clinics (clinic_id, clinic_name, registration_no, address, phone, email, status)
VALUES
    ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'Colombo Heart Centre',    'REG-CHC-001', '45 Galle Road, Colombo 03',   '+94112345678', 'info@chc.lk',     'active'),
    ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'Kandy Medical Institute', 'REG-KMI-002', '12 Peradeniya Road, Kandy',    '+94812345678', 'info@kmi.lk',     'active'),
    ('cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'Sunrise Tele Clinic',     'REG-STC-003', '78 Online Avenue, Colombo 07', '+94112340000', 'info@sunrise.lk', 'active')
ON CONFLICT (clinic_id) DO NOTHING;

-- Doctors linked to auth seed users (22222222-... = dr.anura, 33333333-... = dr.nadee)
INSERT INTO admin.doctors (
    doctor_id, user_id, full_name, medical_registration_no,
    specialization, consultation_mode, verification_status, status,
    bio, experience_years, qualifications, profile_image_url, consultation_fee
) VALUES
    (
        'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
        '22222222-2222-4222-8222-222222222222',
        'Dr. Anura Bandara',
        'SLMC-1001',
        'Cardiology',
        'physical',
        'verified',
        'active',
        'Senior cardiologist with over 15 years of experience in interventional cardiology and heart failure management. Specialises in coronary artery disease and preventive cardiology.',
        15,
        'MBBS (Colombo), MD (Cardiology), MRCP (UK), FCCP',
        NULL,
        2500.00
    ),
    (
        'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
        '33333333-3333-4333-8333-333333333333',
        'Dr. Nadeesha Perera',
        'SLMC-1002',
        'Cardiology',
        'telemedicine',
        'verified',
        'active',
        'Consultant cardiologist offering telemedicine consultations. Special interest in cardiac imaging and echocardiography.',
        10,
        'MBBS (Peradeniya), MD (Cardiology), FRCP (Edin)',
        NULL,
        1500.00
    ),
    (
        'ffffffff-ffff-4fff-8fff-ffffffffffff',
        NULL,
        'Dr. Ruwan Silva',
        'SLMC-2001',
        'General Practice',
        'physical',
        'verified',
        'active',
        NULL,           -- incomplete profile (no bio)
        NULL,           -- incomplete profile (no experience)
        'MBBS (Colombo)',
        NULL,
        1000.00
    )
ON CONFLICT (doctor_id) DO NOTHING;

INSERT INTO admin.doctor_clinic_assignments (doctor_id, clinic_id, status)
VALUES
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'active'),
    ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'active'),
    ('ffffffff-ffff-4fff-8fff-ffffffffffff', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'active')
ON CONFLICT (doctor_id, clinic_id) DO NOTHING;

-- Availability covers every day of the week for easy testing
INSERT INTO admin.doctor_availability (doctor_id, clinic_id, day_of_week, start_time, end_time, slot_duration, consultation_type, status)
VALUES
    -- Dr. Anura: Mon-Sat physical @ Colombo Heart Centre
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'monday',    '08:00', '12:00', 30, 'physical', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'tuesday',   '08:00', '12:00', 30, 'physical', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'wednesday', '08:00', '12:00', 30, 'physical', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'thursday',  '08:00', '12:00', 30, 'physical', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'friday',    '08:00', '12:00', 30, 'physical', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'saturday',  '09:00', '13:00', 30, 'physical', 'active'),

    -- Dr. Nadeesha: Mon-Fri telemedicine @ Sunrise Tele Clinic
    ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'monday',    '10:00', '16:00', 30, 'telemedicine', 'active'),
    ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'tuesday',   '10:00', '16:00', 30, 'telemedicine', 'active'),
    ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'wednesday', '10:00', '16:00', 30, 'telemedicine', 'active'),
    ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'thursday',  '10:00', '16:00', 30, 'telemedicine', 'active'),
    ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'friday',    '10:00', '16:00', 30, 'telemedicine', 'active'),

    -- Dr. Ruwan: Tue/Thu/Sat physical @ Kandy Medical Institute
    ('ffffffff-ffff-4fff-8fff-ffffffffffff', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'tuesday',   '09:00', '14:00', 20, 'physical', 'active'),
    ('ffffffff-ffff-4fff-8fff-ffffffffffff', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'thursday',  '09:00', '14:00', 20, 'physical', 'active'),
    ('ffffffff-ffff-4fff-8fff-ffffffffffff', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'saturday',  '09:00', '13:00', 20, 'physical', 'active')
ON CONFLICT DO NOTHING;

-- Ensure Dr. Anura is telemedicine-enabled (weekday afternoon slots)
INSERT INTO admin.doctor_availability (doctor_id, clinic_id, day_of_week, start_time, end_time, slot_duration, consultation_type, status)
VALUES
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'monday',    '14:00', '17:00', 30, 'telemedicine', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'tuesday',   '14:00', '17:00', 30, 'telemedicine', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'wednesday', '14:00', '17:00', 30, 'telemedicine', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'thursday',  '14:00', '17:00', 30, 'telemedicine', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'friday',    '14:00', '17:00', 30, 'telemedicine', 'active')
ON CONFLICT DO NOTHING;

UPDATE admin.doctors
SET consultation_mode = 'telemedicine'
WHERE doctor_id = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';

INSERT INTO admin.clinic_payment_accounts (clinic_id, provider_name, account_reference, verification_status)
VALUES
    ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'PayHere',   'PAYHERE-CHC-001', 'verified'),
    ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'PayHere',   'PAYHERE-KMI-002', 'verified'),
    ('cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'Stripe',    'STRIPE-STC-003',  'pending')
ON CONFLICT (payment_account_id) DO NOTHING;
