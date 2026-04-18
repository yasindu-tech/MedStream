-- ============================================================
-- CommunicationDB Initialization (medstream_communication)
-- ============================================================

CREATE SCHEMA IF NOT EXISTS communication;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dev_user') THEN
        CREATE ROLE dev_user LOGIN PASSWORD 'dev_password';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE medstream_communication TO dev_user;
GRANT ALL ON SCHEMA communication TO dev_user;

SET search_path TO communication, public;

-- NOTIFICATION_TEMPLATES Table
CREATE TABLE communication.notification_templates (
    template_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) UNIQUE NOT NULL,
    channel VARCHAR(50) NOT NULL,
    subject VARCHAR(255),
    body TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- NOTIFICATIONS Table
CREATE TABLE communication.notifications (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    template_id UUID REFERENCES communication.notification_templates(template_id) ON DELETE SET NULL,
    event_type VARCHAR(100),
    channel VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    message TEXT NOT NULL,
    payload JSONB,
    status VARCHAR(20) DEFAULT 'queued',
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- NOTIFICATION_PREFERENCES Table
CREATE TABLE communication.notification_preferences (
    preference_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL,
    email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sms_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    in_app_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA communication TO dev_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA communication TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA communication GRANT ALL ON TABLES    TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA communication GRANT ALL ON SEQUENCES TO dev_user;

-- Seed Default Templates
INSERT INTO communication.notification_templates (event_type, channel, subject, body, status) VALUES
('appointment.booked', 'email', 'Appointment Confirmed', 'Hello {patient_name}, your appointment with {doctor_name} is confirmed for {date} at {time}.', 'active'),
('appointment.cancelled', 'email', 'Appointment Cancelled', 'Dear {patient_name}, your appointment on {date} has been cancelled.', 'active'),
('appointment.rescheduled', 'email', 'Appointment Rescheduled', 'Hello {patient_name}, your appointment with {doctor_name} has been rescheduled to {date} at {time}.', 'active'),
('appointment.accepted', 'in_app', 'Appointment Accepted', 'Your appointment with {doctor_name} on {date} at {start_time} has been accepted.', 'active'),
('appointment.rejected', 'in_app', 'Appointment Rejected', 'Your appointment with {doctor_name} on {date} at {start_time} was rejected.', 'active'),
('appointment.arrived', 'in_app', 'Appointment Arrival Confirmed', 'Your arrival for appointment {appointment_id} has been recorded.', 'active'),
('appointment.completed', 'in_app', 'Appointment Completed', 'Your appointment with {doctor_name} has been marked as completed.', 'active'),
('appointment.no_show', 'in_app', 'Appointment Marked No-Show', 'Your appointment on {date} at {start_time} was marked as no-show.', 'active'),
('appointment.technical_failure', 'in_app', 'Technical Failure Reported', 'A technical issue was reported for your appointment. Please review details in the app.', 'active'),
('workflow.prescription.trigger', 'in_app', 'Prescription Workflow Started', 'Prescription generation has been triggered for appointment {appointment_id}.', 'active'),
('workflow.followup.trigger', 'in_app', 'Follow-up Workflow Started', 'Follow-up workflow has started for appointment {appointment_id}.', 'active'),
('workflow.reschedule.recommendation', 'in_app', 'Reschedule Recommended', 'A reschedule has been recommended for appointment {appointment_id}.', 'active'),
('account.verification', 'email', 'Verify Your Account', 'Your verification code is: {otp}', 'active'),
('account.password_reset', 'email', 'Reset Your Password', 'Click here to reset your password: {reset_link}', 'active'),
('clinic.admin.onboarding', 'email', 'Welcome to MedStream', '<html><body><h1>Welcome to MedStream</h1><p>Your clinic <strong>{clinic_name}</strong> has been created.</p><p>Use the credentials below to sign in as a clinic administrator:</p><ul><li><strong>Email:</strong> {login_email}</li><li><strong>Temporary password:</strong> {temporary_password}</li></ul><p>Please <a href="{login_url}">sign in now</a> and change your password immediately.</p><p>If you did not request this, please contact support.</p></body></html>', 'active'),
('doctor.verification.approved', 'email', 'Doctor Verification Approved', 'Congratulations {doctor_name}, your verification has been approved. {reason}', 'active'),
('doctor.verification.rejected', 'email', 'Doctor Verification Rejected', 'Hello {doctor_name}, your verification request has been rejected. Reason: {reason}', 'active'),
('doctor.verification.pending', 'in_app', 'Doctor Verification Pending', 'Your verification request is under review. We will notify you once it is processed.', 'active'),
('doctor.profile.created', 'in_app', 'Doctor Profile Created', 'Your doctor profile was created successfully and is now pending verification.', 'active'),
('doctor.profile.updated', 'in_app', 'Doctor Profile Updated', 'Your doctor profile details were updated successfully.', 'active'),
('prescription.available', 'in_app', 'New Prescription', 'Dr. {doctor_name} has issued a new prescription for you.', 'active'),
('payment.confirmed', 'email', 'Payment Received', 'Hello, your payment of {amount} {currency} for appointment {appointment_id} was successful. Transaction: {transaction_reference}', 'active'),
('payment.failed', 'email', 'Payment Failed', 'Your payment of {amount} {currency} failed. Reason: {reason}. You have {retries_remaining} retries left.', 'active'),
('payment.refunded', 'email', 'Refund Processed', 'A refund of {refund_amount} {currency} has been processed for your payment. Reason: {reason}', 'active'),
('patient.profile.updated', 'in_app', 'Profile Updated', 'Your profile was updated successfully. Changed fields: {updated_fields}.', 'active'),
('patient.medical_info.updated', 'in_app', 'Medical Information Updated', 'Your {section} entry ''{item_name}'' was {action}.', 'active'),
('patient.report.uploaded', 'in_app', 'Medical Report Uploaded', 'Your report ''{file_name}'' ({document_type}) was uploaded successfully.', 'active'),
('patient.report.updated', 'in_app', 'Medical Report Updated', 'Your report ''{file_name}'' metadata was updated.', 'active'),
('consultation.summary.available', 'email', 'Your Post-Consultation Care Summary', '{summary_html}', 'active'),
('patient.report.deleted', 'in_app', 'Medical Report Deleted', 'Your report ''{file_name}'' ({document_type}) was removed.', 'active');
