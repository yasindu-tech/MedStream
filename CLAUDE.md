# CLAUDE.md — MedStream Agent Guidelines

> This file defines conventions, architecture rules, and guardrails for AI agents
> working on the MedStream codebase. Read this fully before writing any code.

---

## 1. Project Overview

MedStream is a **healthcare appointment and clinic management platform** built as a
polyglot microservice architecture. All backend services are Python/FastAPI,
containerised with Docker Compose, and sit behind an Nginx API gateway.

---

## 2. Architecture

### 2.1 Service Map

| Service               | DB (schema)              | Host Port | Purpose                                      |
|------------------------|--------------------------|-----------|-----------------------------------------------|
| `auth-service`        | `medstream_auth` (auth)  | 8001      | Registration, login, JWT issuing              |
| `patient-service`     | `medstream_patientcare` (patientcare) | 8002 | Patient profiles, medical records           |
| `clinic-service`      | `medstream_admin` (admin)| 8003      | Clinic CRUD, staff management                 |
| `appointment-service` | `medstream_patientcare` (patientcare) | 8004 | Appointments, doctor search, booked slots   |
| `payment-service`     | `medstream_finance` (finance) | 8005  | Payments, refunds, splits                     |
| `notification-service`| `medstream_communication` (communication) | 8006 | Notifications, templates, preferences    |
| `doctor-service`      | `medstream_admin` (admin)| 8007      | Doctor profiles, availability, search logic   |

### 2.2 Database Boundaries

Each database has its own named PostgreSQL schema. **Services must only query
tables within their own database.** Cross-service data is fetched via internal
HTTP calls, never by cross-DB SQL joins.

| Database                 | Schema           | Shared by                                |
|--------------------------|------------------|------------------------------------------|
| `medstream_auth`         | `auth`           | auth-service                             |
| `medstream_admin`        | `admin`          | clinic-service, doctor-service           |
| `medstream_patientcare`  | `patientcare`    | patient-service, appointment-service     |
| `medstream_finance`      | `finance`        | payment-service                          |
| `medstream_communication`| `communication`  | notification-service                     |

### 2.3 API Gateway (Nginx)

All external traffic enters through `localhost:8080`. Nginx routes by path prefix:

```
/auth/*           → auth-service:8000
/patients/*       → patient-service:8000
/clinics/*        → clinic-service:8000
/appointments/*   → appointment-service:8000
/payments/*       → payment-service:8000
/notifications/*  → notification-service:8000
```

> **Note:** `doctor-service` has no direct gateway route. It is consumed internally
> by other services (e.g., appointment-service calls `http://doctor-service:8000/internal/...`).

### 2.4 Internal vs External Endpoints

- **External** (gateway-exposed): Require JWT auth. Routes match the nginx prefixes above.
- **Internal** (`/internal/*`): Service-to-service only. No JWT required.
  Security is handled by Docker network isolation — nginx is never configured to
  route `/internal/*` paths.

> When adding a new internal endpoint, **do not** add it to `nginx.conf`.

---

## 3. Tech Stack & Versions

| Component      | Version / Library                     |
|----------------|---------------------------------------|
| Python         | 3.12 (slim Docker image)              |
| Web Framework  | FastAPI 0.116.x                       |
| ASGI Server    | Uvicorn 0.35.x                        |
| ORM            | SQLAlchemy 2.0.x (DeclarativeBase)    |
| DB Driver      | psycopg2-binary 2.9.x                |
| Schemas        | Pydantic 2.7.x                        |
| Settings       | pydantic-settings 2.2.x              |
| Auth           | python-jose 3.3.x (HS256 JWT)        |
| Hashing        | passlib 1.7.x + bcrypt 4.0.x         |
| HTTP Client    | httpx 0.27.x (for inter-service calls)|
| Database       | PostgreSQL 15 Alpine                  |
| Gateway        | Nginx 1.27 Alpine                     |

---

## 4. Service Skeleton — File Structure

Every service follows this canonical layout:

```
<service-name>/
├── Dockerfile              # Always: python:3.12-slim, pip install, uvicorn
├── requirements.txt        # Pinned versions, one per line
├── main.py                 # FastAPI app + router registration + /health
└── app/
    ├── __init__.py          # Docstring only (e.g. """Auth service application package.""")
    ├── config.py            # pydantic_settings.BaseSettings + Settings()
    ├── database.py          # SQLAlchemy engine + SessionLocal + Base + get_db()
    ├── middleware/
    │   └── __init__.py      # get_current_user(), require_roles() if service needs JWT
    ├── models/
    │   └── __init__.py      # SQLAlchemy models with __table_args__ = {"schema": "..."}
    ├── schemas/
    │   └── __init__.py      # Pydantic BaseModel classes
    ├── routers/
    │   ├── __init__.py      # Package marker or main router
    │   ├── internal.py      # /internal/* routes (no auth, service-to-service)
    │   └── <feature>.py     # Public routes (JWT protected)
    ├── services/
    │   ├── __init__.py      # Business logic or HTTP clients
    │   └── <name>_client.py # httpx wrappers for calling other services
    └── utils/               # Optional helper modules (e.g. jwt.py, hashing.py)
```

### Rules:
- **`main.py`** lives at the service root (not inside `app/`).
- **`main.py`** always exposes `GET /health` returning `{"status": "ok", "service": "<name>"}`.
- Router registration happens in `main.py` with `app.include_router(...)`.
- Every `__init__.py` in a package directory must exist (even if just a docstring).

---

## 5. Code Conventions

### 5.1 SQLAlchemy Models

```python
from app.database import Base

class MyModel(Base):
    __tablename__ = "my_table"
    __table_args__ = {"schema": "admin"}  # ALWAYS specify the schema explicitly

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # ...
```

- Always use `UUID(as_uuid=True)` for primary keys.
- Use `server_default=func.now()` for timestamps, not `default=`.
- Model `create_type=False` for any PostgreSQL ENUMs already created in init SQL.
- **No Alembic migrations** — schemas are managed by `infrastructure/db/init-*.sql`.

### 5.2 Database Initialization

- All schema DDL and seed data lives in `infrastructure/db/init-*.sql`.
- These SQL files are mounted into the Postgres container via Docker volumes and
  run automatically on first boot.
- When adding new tables, **edit the init SQL file** for the relevant database.
  Do not create migration scripts.
- Always use `ON CONFLICT DO NOTHING` for seed `INSERT` statements.
- Always `GRANT ALL PRIVILEGES` to `dev_user` after creating tables.

### 5.3 Pydantic Schemas

```python
from pydantic import BaseModel

class MyResponse(BaseModel):
    id: UUID
    name: str

    class Config:
        from_attributes = True   # Required for ORM → Pydantic conversion
```

- Use `from __future__ import annotations` at the top for forward refs.
- Response models should always set `from_attributes = True`.

### 5.4 Config / Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://dev_user:dev_password@localhost:<port>/<db>"
    # Add inter-service URLs as needed:
    # OTHER_SERVICE_URL: str = "http://other-service:8000"

    class Config:
        env_file = ".env"

settings = Settings()
```

- Environment variables in `docker-compose.yml` override defaults.
- The `SECRET_KEY` for JWT is shared across all services that verify tokens.
  Default: `your-super-secret-key-change-in-production`.

### 5.5 JWT Authentication

- Auth-service **issues** tokens. Other services **verify** tokens locally.
- JWT payload structure: `{"sub": "<user_id>", "role": "<role>", "type": "access", "exp": ...}`
- Services that need auth copy the middleware pattern from `auth-service/app/middleware/`.
- Use `require_roles("patient", "admin")` as a FastAPI `Depends()` guard.
- **Internal endpoints (`/internal/*`) must NOT require JWT.**

### 5.6 Inter-Service HTTP Calls

```python
import httpx
from app.config import settings

with httpx.Client(timeout=5.0) as client:
    response = client.get(f"{settings.OTHER_SERVICE_URL}/internal/...")
```

- Always use `httpx`, never `requests`.
- Configure the base URL via `config.py` / environment variable (never hardcode).
- Set reasonable timeouts (5s for reads, 10s for search aggregation).
- Handle failures gracefully:
  - **Fail-open** for non-critical data (e.g. slot availability → return empty).
  - **Fail-closed** (502/503) for critical paths (e.g. patient search proxy).

### 5.7 Routers

- Public routers: placed in `app/routers/<feature>.py`, registered without prefix
  (nginx handles the top-level prefix).
- Internal routers: placed in `app/routers/internal.py`, registered with
  `prefix="/internal"`.
- Tag routers appropriately for OpenAPI docs: `APIRouter(tags=["..."])`.

### 5.8 Error Handling

- Return `200` with an empty list for "no results" — **never 404 for search/list endpoints**.
- Use standard HTTP status codes: `400` validation, `401` auth, `403` forbidden,
  `404` resource not found, `409` conflict.
- Raise `HTTPException` in service/router layer. Do not catch exceptions silently.

---

## 6. Docker & Compose

### 6.1 Dockerfile Pattern

All services use the same Dockerfile:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.2 Adding a New Service

1. Create the service directory following the skeleton in §4.
2. Add a `Dockerfile` and `requirements.txt`.
3. Add the service entry in `docker-compose.yml`:
   - Wire to the correct database with `depends_on` + `condition: service_healthy`.
   - Set `DATABASE_URL` and any inter-service URLs as environment variables.
   - Map to a unique host port (`8001`–`800N`).
   - Join `medstream-net` network.
4. Add a route in `api-gateway/nginx.conf` **only if the service has public endpoints**.
5. Add the service to the `api-gateway.depends_on` list.

### 6.3 Running

```bash
# Start everything
docker compose up --build

# Start specific services
docker compose up --build auth-service doctor-service appointment-service

# Rebuild a single service after code changes
docker compose up --build <service-name>
```

---

## 7. Database Quick Reference

### Connecting via DBeaver (or any client)

| Database               | Host      | Port | User     | Password     | DB Name                 |
|------------------------|-----------|------|----------|--------------|-------------------------|
| Auth DB                | localhost | 5432 | postgres | postgres     | medstream_auth          |
| Admin DB               | localhost | 5433 | postgres | postgres     | medstream_admin         |
| Patient Care DB        | localhost | 5434 | postgres | postgres     | medstream_patientcare   |
| Finance DB             | localhost | 5435 | postgres | postgres     | medstream_finance       |
| Communication DB       | localhost | 5436 | postgres | postgres     | medstream_communication |

App user: `dev_user` / `dev_password` (for SQLAlchemy connections).

### Seed Users (auth.users)

| Email                       | Role    | Password  | UUID                                   |
|-----------------------------|---------|-----------|----------------------------------------|
| admin@medstream.lk          | admin   | admin123  | (auto-generated)                       |
| seed.admin@medstream.lk     | admin   | admin123  | 11111111-1111-4111-8111-111111111111   |
| dr.anura@medstream.lk       | doctor  | admin123  | 22222222-2222-4222-8222-222222222222   |
| dr.nadee@medstream.lk       | doctor  | admin123  | 33333333-3333-4333-8333-333333333333   |
| kamal.perera@medstream.lk   | patient | admin123  | 44444444-4444-4444-8444-444444444444   |
| nimali.silva@medstream.lk   | patient | admin123  | 55555555-5555-4555-8555-555555555555   |
| clinic.admin@medstream.lk   | staff   | admin123  | 66666666-6666-4666-8666-666666666666   |
| clinic.staff@medstream.lk   | staff   | admin123  | 77777777-7777-4777-8777-777777777777   |

---

## 8. Things You Must NOT Do

1. **Do not create Alembic migrations.** Schema is managed by init SQL files.
2. **Do not add cross-database SQL joins.** Use internal HTTP endpoints instead.
3. **Do not hardcode service URLs.** Always use `config.py` + environment variables.
4. **Do not expose `/internal/*` routes through nginx.**
5. **Do not add JWT auth to internal endpoints.** Network isolation is the boundary.
6. **Do not return 404 for empty search results.** Return `200` with `[]`.
7. **Do not use `requests` library.** Use `httpx` for HTTP calls.
8. **Do not modify `infrastructure/db/init-*.sql` seed data UUIDs** — other init
   scripts reference them by ID.
9. **Do not add `cd` commands in shell instructions.**
10. **Do not put `main.py` inside `app/`.** It belongs at the service root.

---

## 9. Testing a New Endpoint

```bash
# 1. Login to get a token
TOKEN=$(curl -s -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"kamal.perera@medstream.lk","password":"admin123"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. Call your endpoint
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/appointments/doctors/search?specialty=Cardiology"
```

---

## 10. Commit Message Convention

```
<service>: <short description>

Examples:
  appointment-service: add doctor search endpoint
  infrastructure: add prescriptions table to patientcare DB
  api-gateway: add /telemedicine route
  docs: update CLAUDE.md with new conventions
```
