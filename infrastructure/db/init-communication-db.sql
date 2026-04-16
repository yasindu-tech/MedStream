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
('auth.verification', 'email', 'Verify Your Account', 'Your verification code is: {otp}', 'active'),
('auth.password_reset', 'email', 'Reset Your Password', 'Click here to reset your password: {reset_link}', 'active'),
('prescription.new', 'in_app', 'New Prescription', 'Dr. {doctor_name} has issued a new prescription for you.', 'active')
ON CONFLICT (event_type) DO NOTHING;
