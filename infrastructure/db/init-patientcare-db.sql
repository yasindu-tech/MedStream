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

-- ============================================================
-- Seed data: patients and connected care records
-- ============================================================

INSERT INTO patientcare.patients (
    patient_id, user_id, full_name, dob, gender, nic_passport, phone, address, blood_group
) VALUES
    ('99999999-9999-4999-8999-999999999991', '44444444-4444-4444-8444-444444444444', 'Kamal Perera', '1990-05-12', 'male', '901231234V', '+94-77-111-2233', 'No. 14, Dehiwala', 'O+'),
    ('99999999-9999-4999-8999-999999999992', '55555555-5555-4555-8555-555555555555', 'Nimali Silva', '1988-11-21', 'female', '887654321V', '+94-77-888-1199', 'No. 7, Kandy', 'A-')
ON CONFLICT (patient_id) DO NOTHING;

INSERT INTO patientcare.allergies (
    allergy_id, patient_id, allergy_name, note
) VALUES
    ('a1a1a1a1-a1a1-4a11-8a11-a1a1a1a1a1a1', '99999999-9999-4999-8999-999999999991', 'Penicillin', 'Mild rash'),
    ('a2a2a2a2-a2a2-4a22-8a22-a2a2a2a2a2a2', '99999999-9999-4999-8999-999999999992', 'Peanuts', 'Carries antihistamine')
ON CONFLICT (allergy_id) DO NOTHING;

INSERT INTO patientcare.chronic_conditions (
    condition_id, patient_id, condition_name, note
) VALUES
    ('c1c1c1c1-c1c1-4c11-8c11-c1c1c1c1c1c1', '99999999-9999-4999-8999-999999999991', 'Hypertension', 'On regular medication')
ON CONFLICT (condition_id) DO NOTHING;

INSERT INTO patientcare.medical_documents (
    document_id, patient_id, document_type, file_name, file_url, visibility
) VALUES
    ('d1d1d1d1-d1d1-4d11-8d11-d1d1d1d1d1d1', '99999999-9999-4999-8999-999999999991', 'lab_report', 'cholesterol-report.pdf', 'https://example.local/files/cholesterol-report.pdf', 'doctor_only')
ON CONFLICT (document_id) DO NOTHING;

INSERT INTO patientcare.appointments (
    appointment_id, patient_id, doctor_id, clinic_id, appointment_type,
    appointment_date, start_time, end_time, status, payment_status
) VALUES
    ('abababab-abab-4ab1-8ab1-ababababab11', '99999999-9999-4999-8999-999999999991', 'dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'physical', '2026-04-20', '09:30', '10:00', 'scheduled', 'pending'),
    ('abababab-abab-4ab1-8ab1-ababababab12', '99999999-9999-4999-8999-999999999992', 'dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'telemedicine', '2026-04-23', '14:00', '14:30', 'scheduled', 'paid'),
    ('abababab-abab-4ab1-8ab1-ababababab13', '99999999-9999-4999-8999-999999999991', 'dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'physical', '2026-04-21', '11:00', '11:20', 'completed', 'paid')
ON CONFLICT (appointment_id) DO NOTHING;

INSERT INTO patientcare.appointment_status_history (
    history_id, appointment_id, old_status, new_status, changed_by, reason
) VALUES
    ('b1b1b1b1-b1b1-41b1-81b1-b1b1b1b1b1b1', 'abababab-abab-4ab1-8ab1-ababababab13', 'scheduled', 'completed', 'system', 'Consultation finished')
ON CONFLICT (history_id) DO NOTHING;

INSERT INTO patientcare.telemedicine_sessions (
    session_id, appointment_id, provider_name, meeting_link, status
) VALUES
    ('c2c2c2c2-c2c2-42c2-82c2-c2c2c2c2c2c2', 'abababab-abab-4ab1-8ab1-ababababab12', 'Zoom', 'https://zoom.us/j/medstream-demo-123', 'scheduled')
ON CONFLICT (session_id) DO NOTHING;

INSERT INTO patientcare.consultation_notes (
    note_id, appointment_id, patient_id, doctor_id, diagnosis, symptoms, advice
) VALUES
    (
        'd3d3d3d3-d3d3-43d3-83d3-d3d3d3d3d3d3',
        'abababab-abab-4ab1-8ab1-ababababab13',
        '99999999-9999-4999-8999-999999999991',
        (SELECT doctor_id FROM patientcare.appointments WHERE appointment_id = 'abababab-abab-4ab1-8ab1-ababababab13'),
        'Seasonal dermatitis',
        'Itchy skin on forearm',
        'Use moisturizer twice daily and avoid harsh soaps'
    )
ON CONFLICT (note_id) DO NOTHING;

INSERT INTO patientcare.prescriptions (
    prescription_id, appointment_id, patient_id, doctor_id, notes
) VALUES
    (
        'e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e4',
        'abababab-abab-4ab1-8ab1-ababababab13',
        '99999999-9999-4999-8999-999999999991',
        (SELECT doctor_id FROM patientcare.appointments WHERE appointment_id = 'abababab-abab-4ab1-8ab1-ababababab13'),
        'Take after meals'
    )
ON CONFLICT (prescription_id) DO NOTHING;

INSERT INTO patientcare.prescription_items (
    prescription_item_id, prescription_id, medicine_name, dosage, frequency, duration, instruction
) VALUES
    ('f5f5f5f5-f5f5-45f5-85f5-f5f5f5f5f5f5', 'e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e4', 'Cetirizine', '10mg', 'Once daily', '5 days', 'Take at night')
ON CONFLICT (prescription_item_id) DO NOTHING;
