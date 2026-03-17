-- Create logical databases for local development
CREATE DATABASE medstream_auth;
CREATE DATABASE medstream_clinic;
CREATE DATABASE medstream_payments;

-- Create shared local developer user
CREATE USER dev_user WITH PASSWORD 'dev_password';

-- Grant database-level privileges
GRANT ALL PRIVILEGES ON DATABASE medstream_auth TO dev_user;
GRANT ALL PRIVILEGES ON DATABASE medstream_clinic TO dev_user;
GRANT ALL PRIVILEGES ON DATABASE medstream_payments TO dev_user;
