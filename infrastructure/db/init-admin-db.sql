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
<<<<<<< Updated upstream
=======
ALTER DEFAULT PRIVILEGES IN SCHEMA admin GRANT ALL ON SEQUENCES TO dev_user;

-- ============================================================
-- Seed data: clinics, doctors, assignments, availability
-- ============================================================

INSERT INTO admin.clinics (
    clinic_id, clinic_name, registration_no, address, phone, email, status
) VALUES
    ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1', 'Colombo Central Clinic', 'CL-REG-001', 'No. 10, Galle Road, Colombo 03', '+94-11-200-3000', 'colombo.central@medstream.lk', 'active'),
    ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2', 'Kandy Family Care', 'CL-REG-002', 'No. 22, Peradeniya Road, Kandy', '+94-81-220-3300', 'kandy.family@medstream.lk', 'active')
ON CONFLICT (clinic_id) DO NOTHING;

INSERT INTO admin.clinic_admins (
    clinic_admin_id, clinic_id, user_id, status
) VALUES
    ('acacacac-aaaa-4aca-8aca-aaaaaaaaaaa1', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1', '66666666-6666-4666-8666-666666666666', 'active')
ON CONFLICT (clinic_admin_id) DO NOTHING;

INSERT INTO admin.clinic_staff (
    staff_id, clinic_id, user_id, staff_role, status
) VALUES
    ('bcbcbcbc-bbbb-4bcb-8bcb-bbbbbbbbbbb1', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1', '77777777-7777-4777-8777-777777777777', 'receptionist', 'active')
ON CONFLICT (staff_id) DO NOTHING;

INSERT INTO admin.doctors (
    doctor_id, user_id, full_name, medical_registration_no, specialization,
    consultation_mode, verification_status, status
) VALUES
    ('dddddddd-dddd-4ddd-8ddd-ddddddddddd1', '22222222-2222-4222-8222-222222222222', 'Dr. Anura Jayasinghe', 'SLMC-1001', 'Cardiology', 'physical,telemedicine', 'verified', 'active'),
    ('dddddddd-dddd-4ddd-8ddd-ddddddddddd2', '33333333-3333-4333-8333-333333333333', 'Dr. Nadee Fernando', 'SLMC-1002', 'Dermatology', 'physical', 'verified', 'active')
ON CONFLICT (doctor_id) DO NOTHING;

INSERT INTO admin.doctor_clinic_assignments (
    assignment_id, doctor_id, clinic_id, status
) VALUES
    ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeee1', 'dddddddd-dddd-4ddd-8ddd-ddddddddddd1', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1', 'active'),
    ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeee2', 'dddddddd-dddd-4ddd-8ddd-ddddddddddd2', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2', 'active')
ON CONFLICT (assignment_id) DO NOTHING;

INSERT INTO admin.doctor_availability (
    availability_id, doctor_id, clinic_id, day_of_week, start_time, end_time,
    slot_duration, consultation_type, status
) VALUES
    ('f1f1f1f1-f1f1-4f11-8f11-f1f1f1f1f1f1', 'dddddddd-dddd-4ddd-8ddd-ddddddddddd1', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1', 'monday', '09:00', '13:00', 30, 'physical', 'active'),
    ('f2f2f2f2-f2f2-4f22-8f22-f2f2f2f2f2f2', 'dddddddd-dddd-4ddd-8ddd-ddddddddddd1', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1', 'wednesday', '14:00', '17:00', 30, 'telemedicine', 'active'),
    ('f3f3f3f3-f3f3-4f33-8f33-f3f3f3f3f3f3', 'dddddddd-dddd-4ddd-8ddd-ddddddddddd2', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2', 'tuesday', '10:00', '15:00', 20, 'physical', 'active')
ON CONFLICT (availability_id) DO NOTHING;

INSERT INTO admin.clinic_payment_accounts (
    payment_account_id, clinic_id, provider_name, account_reference, verification_status
) VALUES
    ('abababab-abab-4aba-8aba-ababababab01', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1', 'Stripe', 'acct_colombo_001', 'verified'),
    ('abababab-abab-4aba-8aba-ababababab02', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2', 'PayHere', 'acct_kandy_002', 'verified')
ON CONFLICT (payment_account_id) DO NOTHING;
>>>>>>> Stashed changes
