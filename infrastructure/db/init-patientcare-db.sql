-- ============================================================
-- PatientCareDB Initialization (medstream_patientcare)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dev_user') THEN
        CREATE ROLE dev_user LOGIN PASSWORD 'dev_password';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE medstream_patientcare TO dev_user;

CREATE SCHEMA IF NOT EXISTS patientcare;
GRANT ALL ON SCHEMA patientcare TO dev_user;

-- ============================================================
-- Tables
-- ============================================================

CREATE TABLE patientcare.patients (
    patient_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid UNIQUE,
    email varchar(255) UNIQUE,
    full_name varchar(255) NOT NULL,
    dob date,
    gender varchar(20),
    nic_passport varchar(50) UNIQUE,
    phone varchar(30),
    address text,
    blood_group varchar(10),
    emergency_contact varchar(255),
    profile_image_url text,
    pending_email varchar(255),
    profile_status varchar(30) NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patientcare.allergies (
    allergy_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE,
    allergy_name varchar(255) NOT NULL,
    note text
);

CREATE TABLE patientcare.chronic_conditions (
    condition_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE,
    condition_name varchar(255) NOT NULL,
    note text
);

CREATE TABLE patientcare.medical_documents (
    document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE,
    appointment_id uuid,
    document_type varchar(100) NOT NULL,
    file_name varchar(255) NOT NULL,
    file_url text NOT NULL,
    visibility varchar(30) NOT NULL DEFAULT 'private',
    description text,
    uploaded_by varchar(50),
    uploaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patientcare.appointments (
    appointment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_appointment_id uuid REFERENCES patientcare.appointments(appointment_id) ON DELETE SET NULL,
    patient_id uuid NOT NULL REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE,
    doctor_id uuid,
    doctor_name varchar(150),
    clinic_id uuid,
    clinic_name varchar(150),
    appointment_type varchar(50) NOT NULL,
    appointment_date date NOT NULL,
    start_time time NOT NULL,
    end_time time NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'scheduled',
    payment_status varchar(30) NOT NULL DEFAULT 'pending',
    completed_at timestamptz,
    completed_by varchar(100),
    no_show_at timestamptz,
    no_show_marked_by varchar(100),
    technical_failure_at timestamptz,
    technical_failure_reason text,
    technical_failure_marked_by varchar(100),
    cancellation_reason text,
    cancelled_by varchar(30),
    rescheduled_from_date date,
    rescheduled_from_start_time time,
    reschedule_count int NOT NULL DEFAULT 0,
    policy_id uuid,
    idempotency_key varchar(255),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_appointments_patient_idempotency UNIQUE (patient_id, idempotency_key)
);

CREATE TABLE patientcare.appointment_status_history (
    history_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id uuid NOT NULL REFERENCES patientcare.appointments(appointment_id) ON DELETE CASCADE,
    old_status varchar(30),
    new_status varchar(30) NOT NULL,
    changed_by varchar(100),
    reason text,
    changed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patientcare.telemedicine_sessions (
    session_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id uuid NOT NULL UNIQUE REFERENCES patientcare.appointments(appointment_id) ON DELETE CASCADE,
    provider_name varchar(100),
    meeting_link text,
    status varchar(30) NOT NULL DEFAULT 'scheduled',
    session_version int NOT NULL DEFAULT 1,
    token_version int NOT NULL DEFAULT 1,
    started_at timestamptz,
    ended_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patientcare.telemedicine_session_events (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES patientcare.telemedicine_sessions(session_id) ON DELETE CASCADE,
    event_type varchar(50) NOT NULL,
    actor varchar(100),
    details text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patientcare.google_oauth_integrations (
    integration_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider varchar(50) NOT NULL UNIQUE,
    account_email varchar(255),
    refresh_token text NOT NULL,
    scope text,
    token_type varchar(50),
    is_active int NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patientcare.consultation_notes (
    note_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id uuid NOT NULL UNIQUE REFERENCES patientcare.appointments(appointment_id) ON DELETE CASCADE,
    patient_id uuid NOT NULL REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE,
    doctor_id uuid,
    diagnosis text,
    symptoms text,
    advice text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patientcare.prescriptions (
    prescription_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id uuid NOT NULL UNIQUE REFERENCES patientcare.appointments(appointment_id) ON DELETE CASCADE,
    patient_id uuid NOT NULL REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE,
    doctor_id uuid,
    clinic_id uuid,
    medications jsonb NOT NULL DEFAULT '[]',
    instructions text,
    notes text,
    status varchar(30) NOT NULL DEFAULT 'draft',
    issued_at timestamptz,
    finalized_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patientcare.appointment_notes (
    note_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id uuid NOT NULL REFERENCES patientcare.appointments(appointment_id) ON DELETE CASCADE,
    doctor_id uuid NOT NULL,
    content text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patientcare.consultation_summaries (
    summary_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id uuid NOT NULL UNIQUE REFERENCES patientcare.appointments(appointment_id) ON DELETE CASCADE,
    patient_id uuid NOT NULL REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE,
    status varchar(30) NOT NULL DEFAULT 'generated',
    llm_used boolean NOT NULL DEFAULT false,
    doctor_name varchar(255),
    diagnosis text,
    medications jsonb NOT NULL DEFAULT '[]',
    sections jsonb NOT NULL DEFAULT '[]',
    summary_text text NOT NULL,
    summary_html text NOT NULL,
    missing_fields jsonb NOT NULL DEFAULT '[]',
    warnings jsonb NOT NULL DEFAULT '[]',
    generated_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patientcare.follow_up_suggestions (
    suggestion_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    original_appointment_id uuid NOT NULL REFERENCES patientcare.appointments(appointment_id) ON DELETE CASCADE,
    doctor_id uuid NOT NULL,
    patient_id uuid NOT NULL REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE,
    clinic_id uuid,
    suggested_date date NOT NULL,
    suggested_start_time time NOT NULL,
    suggested_end_time time NOT NULL,
    consultation_type varchar(50) NOT NULL,
    notes text,
    status varchar(30) NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patientcare.appointment_policies (
    policy_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cancellation_window_hours int NOT NULL,
    reschedule_window_hours int NOT NULL,
    advance_booking_days int NOT NULL,
    no_show_grace_period_minutes int NOT NULL,
    max_reschedules int NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_by varchar(100),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patientcare.appointment_policy_history (
    history_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    old_policy_id uuid,
    new_policy_id uuid NOT NULL,
    changed_by varchar(100),
    reason text,
    changed_at timestamptz NOT NULL DEFAULT now()
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA patientcare TO dev_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA patientcare TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA patientcare GRANT ALL ON TABLES TO dev_user;

-- ============================================================
-- Seed Data
-- ============================================================

INSERT INTO patientcare.patients (patient_id, user_id, email, full_name, dob, gender, nic_passport, phone, address, blood_group)
VALUES
    ('99999999-9999-4999-8999-999999999991', '44444444-4444-4444-8444-444444444444', 'kamal.perera@medstream.lk', 'Kamal Perera', '1990-05-12', 'male', '901231234V', '+94-77-111-2233', 'No. 14, Dehiwala', 'O+'),
    ('99999999-9999-4999-8999-999999999992', '55555555-5555-4555-8555-555555555555', 'nimali.silva@medstream.lk', 'Nimali Silva', '1988-11-21', 'female', '887654321V', '+94-77-888-1199', 'No. 7, Kandy', 'A-');

INSERT INTO patientcare.allergies (patient_id, allergy_name, note)
VALUES
    ('99999999-9999-4999-8999-999999999991', 'Penicillin', 'Mild rash'),
    ('99999999-9999-4999-8999-999999999992', 'Peanuts', 'Carries antihistamine');

INSERT INTO patientcare.chronic_conditions (patient_id, condition_name, note)
VALUES
    ('99999999-9999-4999-8999-999999999991', 'Hypertension', 'On regular medication');

INSERT INTO patientcare.appointments (appointment_id, patient_id, doctor_id, clinic_id, appointment_type, appointment_date, start_time, end_time, status, payment_status)
VALUES
    ('abababab-abab-4ab1-8ab1-ababababab11', '99999999-9999-4999-8999-999999999991', 'dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'physical', '2026-04-20', '09:30', '10:00', 'scheduled', 'pending'),
    ('abababab-abab-4ab1-8ab1-ababababab12', '99999999-9999-4999-8999-999999999992', 'dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'telemedicine', '2026-04-23', '14:00', '14:30', 'scheduled', 'paid'),
    ('abababab-abab-4ab1-8ab1-ababababab13', '99999999-9999-4999-8999-999999999991', 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'physical', '2026-04-21', '11:00', '11:20', 'completed', 'paid');

INSERT INTO patientcare.appointment_status_history (appointment_id, old_status, new_status, changed_by, reason)
VALUES
    ('abababab-abab-4ab1-8ab1-ababababab13', 'scheduled', 'completed', 'system', 'Consultation finished');

INSERT INTO patientcare.appointment_policies (policy_id, cancellation_window_hours, reschedule_window_hours, advance_booking_days, no_show_grace_period_minutes, max_reschedules, is_active, created_by)
VALUES
    ('12121212-1212-4121-8121-121212121212', 12, 24, 14, 15, 2, true, 'system');
