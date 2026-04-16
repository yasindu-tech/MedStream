-- Create Schema
CREATE SCHEMA IF NOT EXISTS communication;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create dev_user if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dev_user') THEN
        CREATE ROLE dev_user LOGIN PASSWORD 'dev_password';
    END IF;
END
$$;

-- Grant permissions
GRANT CONNECT ON DATABASE medstream_communication TO dev_user;
GRANT ALL ON SCHEMA communication TO dev_user;

-- Set Search Path
SET search_path TO communication, public;

-- NOTIFICATION_TEMPLATES Table
CREATE TABLE IF NOT EXISTS notification_templates (
    template_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) UNIQUE NOT NULL,
    channel VARCHAR(50) NOT NULL, -- e.g. "email", "sms", "in_app"
    subject VARCHAR(255),
    body TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- NOTIFICATIONS Table (Combines queue and history)
CREATE TABLE IF NOT EXISTS notifications (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    template_id UUID REFERENCES notification_templates(template_id),
    event_type VARCHAR(100),
    channel VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    message TEXT NOT NULL,
    payload JSONB,
    status VARCHAR(20) DEFAULT 'queued', -- queued, sent, failed, read
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Backward-compatible migration for older notification schema variants.
ALTER TABLE IF EXISTS communication.notifications
    ADD COLUMN IF NOT EXISTS event_type VARCHAR(100),
    ADD COLUMN IF NOT EXISTS title VARCHAR(255),
    ADD COLUMN IF NOT EXISTS message TEXT;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        WHERE tc.constraint_schema = 'communication'
          AND tc.table_name = 'notifications'
          AND tc.constraint_name = 'fk_notifications_template'
    ) THEN
        ALTER TABLE communication.notifications
            DROP CONSTRAINT fk_notifications_template;
    END IF;
END
$$;

ALTER TABLE IF EXISTS communication.notifications
    ADD CONSTRAINT fk_notifications_template
    FOREIGN KEY (template_id)
    REFERENCES communication.notification_templates(template_id)
    ON DELETE SET NULL;

-- NOTIFICATION_PREFERENCES Table
CREATE TABLE IF NOT EXISTS notification_preferences (
    preference_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL,
    email_enabled BOOLEAN DEFAULT TRUE,
    sms_enabled BOOLEAN DEFAULT TRUE,
    in_app_enabled BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Grant privileges on all existing and future tables
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA communication TO dev_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA communication TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA communication GRANT ALL ON TABLES    TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA communication GRANT ALL ON SEQUENCES TO dev_user;

-- Seed Default Templates (Initial Boot)
INSERT INTO notification_templates (event_type, channel, subject, body, status) VALUES
('appointment.booked', 'email', 'Appointment Confirmed', 'Hello {patient_name}, your appointment with {doctor_name} is confirmed for {date} at {time}.', 'active'),
('appointment.cancelled', 'email', 'Appointment Cancelled', 'Dear {patient_name}, your appointment on {date} has been cancelled.', 'active'),
('account.verification', 'email', 'Verify Your Account', 'Your verification code is: {otp}', 'active'),
('account.password_reset', 'email', 'Reset Your Password', 'Click here to reset your password: {reset_link}', 'active'),
('clinic.admin.onboarding', 'email', 'Welcome to MedStream', '<html><body><h1>Welcome to MedStream</h1><p>Your clinic <strong>{clinic_name}</strong> has been created.</p><p>Use the credentials below to sign in as a clinic administrator:</p><ul><li><strong>Email:</strong> {login_email}</li><li><strong>Temporary password:</strong> {temporary_password}</li></ul><p>Please <a href="{login_url}">sign in now</a> and change your password immediately.</p><p>If you did not request this, please contact support.</p></body></html>', 'active'),
('prescription.available', 'in_app', 'New Prescription', 'Dr. {doctor_name} has issued a new prescription for you.', 'active')
ON CONFLICT (event_type) DO NOTHING;
