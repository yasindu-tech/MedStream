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

CREATE TABLE IF NOT EXISTS admin.doctors (
    doctor_id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                  uuid,
    full_name                varchar(255) NOT NULL,
    medical_registration_no  varchar(120),
    specialization           varchar(120),
    consultation_mode        varchar(40),
    verification_status      varchar(30) NOT NULL DEFAULT 'verified',
    status                   varchar(30) NOT NULL DEFAULT 'active',
    created_at               timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admin.doctor_clinic_assignments (
    assignment_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id      uuid NOT NULL,
    clinic_id      uuid NOT NULL,
    status         varchar(30) NOT NULL DEFAULT 'active',
    created_at     timestamptz NOT NULL DEFAULT now(),
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

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA admin TO dev_user;
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
INSERT INTO admin.doctors (doctor_id, user_id, full_name, medical_registration_no, specialization, consultation_mode, verification_status, status)
VALUES
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', '22222222-2222-4222-8222-222222222222', 'Dr. Anura Bandara', 'SLMC-1001', 'Cardiology',        'physical',     'verified', 'active'),
    ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', '33333333-3333-4333-8333-333333333333', 'Dr. Nadeesha Perera', 'SLMC-1002', 'Cardiology',      'telemedicine', 'verified', 'active'),
    ('ffffffff-ffff-4fff-8fff-ffffffffffff', NULL,                                    'Dr. Ruwan Silva',    'SLMC-2001', 'General Practice', 'physical',     'verified', 'active')
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
    -- Dr. Anura: Mon–Sat physical @ Colombo Heart Centre
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'monday',    '08:00', '12:00', 30, 'physical', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'tuesday',   '08:00', '12:00', 30, 'physical', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'wednesday', '08:00', '12:00', 30, 'physical', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'thursday',  '08:00', '12:00', 30, 'physical', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'friday',    '08:00', '12:00', 30, 'physical', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'saturday',  '09:00', '13:00', 30, 'physical', 'active'),

    -- Dr. Nadeesha: Mon–Fri telemedicine @ Sunrise Tele Clinic
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
