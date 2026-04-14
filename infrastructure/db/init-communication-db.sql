-- ============================================================
-- CommunicationDB Initialization (medstream_communication)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dev_user') THEN
        CREATE ROLE dev_user LOGIN PASSWORD 'dev_password';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE medstream_communication TO dev_user;

CREATE SCHEMA IF NOT EXISTS communication;
GRANT ALL ON SCHEMA communication TO dev_user;

CREATE TABLE IF NOT EXISTS communication.templates (
    template_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    template_key varchar(120) NOT NULL UNIQUE,
    channel varchar(30) NOT NULL,
    subject varchar(255),
    body text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS communication.notification_preferences (
    preference_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    channel varchar(30) NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_notification_pref UNIQUE (user_id, channel)
);

CREATE TABLE IF NOT EXISTS communication.notifications (
    notification_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid,
    template_id uuid,
    channel varchar(30) NOT NULL,
    payload jsonb,
    status varchar(30) NOT NULL DEFAULT 'queued',
    sent_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_notifications_template FOREIGN KEY (template_id) REFERENCES communication.templates(template_id) ON DELETE SET NULL
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA communication TO dev_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA communication GRANT ALL ON TABLES TO dev_user;
