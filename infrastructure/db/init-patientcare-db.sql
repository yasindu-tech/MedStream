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

CREATE TABLE IF NOT EXISTS patientcare.patients (
    patient_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid,
    full_name varchar(255) NOT NULL,
    dob date,
    gender varchar(20),
    nic_passport varchar(50),
    phone varchar(30),
    address text,
    blood_group varchar(10),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_patients_nic_passport UNIQUE (nic_passport)
);

CREATE TABLE IF NOT EXISTS patientcare.allergies (
    allergy_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL,
    allergy_name varchar(255) NOT NULL,
    note text,
    CONSTRAINT fk_allergies_patient FOREIGN KEY (patient_id) REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS patientcare.chronic_conditions (
    condition_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL,
    condition_name varchar(255) NOT NULL,
    note text,
    CONSTRAINT fk_conditions_patient FOREIGN KEY (patient_id) REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS patientcare.medical_documents (
    document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL,
    document_type varchar(100) NOT NULL,
    file_name varchar(255) NOT NULL,
    file_url text NOT NULL,
    visibility varchar(30) NOT NULL DEFAULT 'private',
    uploaded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_documents_patient FOREIGN KEY (patient_id) REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS patientcare.appointments (
    appointment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_appointment_id uuid,
    patient_id uuid NOT NULL,
    doctor_id uuid,
    clinic_id uuid,
    appointment_type varchar(50) NOT NULL,
    appointment_date date NOT NULL,
    start_time time NOT NULL,
    end_time time NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'scheduled',
    payment_status varchar(30) NOT NULL DEFAULT 'pending',
    cancellation_reason text,
    cancelled_by varchar(30),
    rescheduled_from_date date,
    rescheduled_from_start_time time,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_appointments_patient FOREIGN KEY (patient_id) REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE,
    CONSTRAINT fk_appointments_parent FOREIGN KEY (parent_appointment_id) REFERENCES patientcare.appointments(appointment_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS patientcare.appointment_status_history (
    history_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id uuid NOT NULL,
    old_status varchar(30),
    new_status varchar(30) NOT NULL,
    changed_by varchar(100),
    reason text,
    changed_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_status_history_appointment FOREIGN KEY (appointment_id) REFERENCES patientcare.appointments(appointment_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS patientcare.telemedicine_sessions (
    session_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id uuid NOT NULL UNIQUE,
    provider_name varchar(100),
    meeting_link text,
    status varchar(30) NOT NULL DEFAULT 'scheduled',
    started_at timestamptz,
    ended_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_telemed_appointment FOREIGN KEY (appointment_id) REFERENCES patientcare.appointments(appointment_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS patientcare.consultation_notes (
    note_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id uuid NOT NULL UNIQUE,
    patient_id uuid NOT NULL,
    doctor_id uuid,
    diagnosis text,
    symptoms text,
    advice text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_notes_appointment FOREIGN KEY (appointment_id) REFERENCES patientcare.appointments(appointment_id) ON DELETE CASCADE,
    CONSTRAINT fk_notes_patient FOREIGN KEY (patient_id) REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS patientcare.prescriptions (
    prescription_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id uuid NOT NULL UNIQUE,
    patient_id uuid NOT NULL,
    doctor_id uuid,
    notes text,
    issued_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_prescriptions_appointment FOREIGN KEY (appointment_id) REFERENCES patientcare.appointments(appointment_id) ON DELETE CASCADE,
    CONSTRAINT fk_prescriptions_patient FOREIGN KEY (patient_id) REFERENCES patientcare.patients(patient_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS patientcare.prescription_items (
    prescription_item_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    prescription_id uuid NOT NULL,
    medicine_name varchar(255) NOT NULL,
    dosage varchar(100),
    frequency varchar(100),
    duration varchar(100),
    instruction text,
    CONSTRAINT fk_prescription_items_prescription FOREIGN KEY (prescription_id) REFERENCES patientcare.prescriptions(prescription_id) ON DELETE CASCADE
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA patientcare TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA patientcare GRANT ALL ON TABLES TO dev_user;
