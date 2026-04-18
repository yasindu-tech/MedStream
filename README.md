# MedStream Full Deployment Guide

This document lists the steps to deploy the full MedStream website locally, including:

- All backend microservices and databases from this repository.
- API gateway routing.
- Frontend app from the sibling workspace folder: `../medstream-frontend`.

## Architecture Overview

### Backend Services (Docker Compose)

- api-gateway (nginx): host port `8080`
- auth-service: host port `8001`
- patient-service: host port `8002`
- clinic-service: host port `8003`
- appointment-service: host port `8004`
- payment-service: host port `8005`
- notification-service: host port `8006`
- doctor-service: host port `8007`
- telemedicine-service: host port `8008`
- ai-service: host port `8009`

### Databases

Five PostgreSQL containers are used:

- auth_db (`medstream_auth`) on host `5432`
- admin_db (`medstream_admin`) on host `5433`
- patientcare_db (`medstream_patientcare`) on host `5434`
- finance_db (`medstream_finance`) on host `5435`
- communication_db (`medstream_communication`) on host `5436`

### Frontend

- Vite React app in sibling folder: `../medstream-frontend`
- Default dev port: `5173`
- Default API target in code: `http://localhost:8080`

## Prerequisites

Install these before deployment:

1. Docker Desktop (with Compose v2)
2. Node.js 20+ and npm
3. Git

Validate tools:

```bash
docker --version
docker compose version
node --version
npm --version
```

## Step 1: Clone Repositories

Your workspace should contain both folders side by side:

```text
GitHub/
  MedStream/
  medstream-frontend/
```

If not already cloned:

```bash
cd /Users/nethalfernando/Documents/GitHub
git clone <backend-repo-url> MedStream
git clone <frontend-repo-url> medstream-frontend
```

## Step 2: Configure Required Environment Variables

From `MedStream/`, create a root `.env` file for compose-level variables:

```bash
cd /Users/nethalfernando/Documents/GitHub/MedStream
cat > .env << 'EOF'
INTERNAL_API_TOKEN=change-me-in-dev
INTERNAL_SERVICE_TOKEN=medstream-internal-token
SECRET_KEY=your-super-secret-key-change-in-production
JWT_SECRET=your-super-secret-key-change-in-production

# Optional integrations
GEMINI_API_KEY=
GEMINI_MODEL=gemini-flash-latest
CHATBOT_ENABLE_LLM=true

CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
CLOUDINARY_FOLDER=medstream/patient-documents

TELEMEDICINE_PROVIDER=google
MEETING_LINK_BASE_URL=https://meet.medstream.local/s
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8080/telemedicine/auth/google/callback
GOOGLE_OAUTH_SCOPES=https://www.googleapis.com/auth/meetings.space.created
EOF
```

Notes:

- `notification-service` also loads `notification-service/app/.env` via `env_file` in compose.
- Keep secrets out of git for non-local environments.

## Step 3: Start Backend + Databases + Gateway

From `MedStream/`:

```bash
docker compose down -v
docker compose up --build -d
```

Why `down -v` first:

- Ensures init SQL scripts run against empty DB volumes.
- Produces a clean deployment state.

Check status:

```bash
docker compose ps
```

## Step 4: Verify Backend Deployment

Gateway base URL:

- `http://localhost:8080`

Health checks via gateway:

```bash
curl http://localhost:8080/auth/health
curl http://localhost:8080/patients/health
curl http://localhost:8080/clinics/health
curl http://localhost:8080/appointments/health
curl http://localhost:8080/doctors/health
curl http://localhost:8080/telemedicine/health
curl http://localhost:8080/payments/health
curl http://localhost:8080/notifications/health
```

Optional direct service checks:

```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:8005/health
curl http://localhost:8006/health
curl http://localhost:8007/health
curl http://localhost:8008/health
curl http://localhost:8009/health
```

## Step 5: Deploy Frontend

In a new terminal:

```bash
cd /Users/nethalfernando/Documents/GitHub/medstream-frontend
```

Create frontend env file:

```bash
cat > .env.local << 'EOF'
VITE_API_BASE_URL=http://localhost:8080
VITE_API_URL=http://localhost:8080
EOF
```

Install dependencies and run:

```bash
npm install
npm run dev -- --host
```

Open:

- `http://localhost:5173`

The frontend will call backend APIs through the gateway at `http://localhost:8080`.

## Step 6: Production-Style Frontend Build (Optional)

```bash
cd /Users/nethalfernando/Documents/GitHub/medstream-frontend
npm run build
npm run preview -- --host
```

Then open the preview URL shown in terminal (typically `http://localhost:4173`).

## Common Operations

### View Logs

```bash
cd /Users/nethalfernando/Documents/GitHub/MedStream
docker compose logs -f api-gateway
docker compose logs -f auth-service
docker compose logs -f notification-service
```

### Restart One Service

```bash
cd /Users/nethalfernando/Documents/GitHub/MedStream
docker compose up -d --build appointment-service
```

### Stop Everything

Backend:

```bash
cd /Users/nethalfernando/Documents/GitHub/MedStream
docker compose down
```

Frontend:

- Stop with `Ctrl+C` in the frontend terminal.

### Full Reset (Clean Re-deploy)

```bash
cd /Users/nethalfernando/Documents/GitHub/MedStream
docker compose down -v
docker compose up --build -d
```

## Troubleshooting

1. Port already in use:
   - Stop conflicting process/container using the same port (`8080`, `5173`, `5432`-`5436`, `8001`-`8009`).

2. Service keeps restarting:
   - Check logs: `docker compose logs <service-name>`.

3. Frontend cannot reach backend:
   - Confirm gateway is up on `http://localhost:8080`.
   - Confirm `.env.local` in frontend has `VITE_API_BASE_URL` or `VITE_API_URL`.

4. DB schema/data issues:
   - Recreate volumes: `docker compose down -v && docker compose up --build -d`.

5. Optional integrations failing (Google, Gemini, Cloudinary):
   - Leave env vars empty for local core flows, or provide valid credentials.

## Kubernetes Placeholder

Kubernetes ingress skeleton exists at:

- `infrastructure/k8s/ingress-routes.yaml`

This repository currently provides ingress route definitions only. Full k8s deployment manifests for every service/database are not yet defined.

## Deployment Checklist

1. Backend containers up (`docker compose ps`).
2. All gateway health endpoints return `{"status":"ok", ...}`.
3. Frontend running on `http://localhost:5173`.
4. Frontend login/API flows succeed against `http://localhost:8080`.
5. Notification websocket and protected routes are reachable through gateway.