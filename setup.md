
# Developer Setup Guide — MedStream

This guide walks you through setting up the local development environment with logical databases for the four-developer team.

## Prerequisites

- Docker and Docker Compose installed
- Git cloned with this repository
- Terminal access (zsh, bash, etc.)

## Database Architecture

MedStream uses a **PostgreSQL instance with three logical databases** to separate concerns:

| Database | Purpose | Services |
|----------|---------|----------|
| `medstream_auth` | Authentication, user credentials | auth-service |
| `medstream_clinic` | Clinics, patients, appointments | clinic-service, patient-service, appointment-service, notification-service |
| `medstream_payments` | Payment transactions, invoices | payment-service |

**Shared Developer Credentials:**
- Username: `dev_user`
- Password: `dev_password`
- Host: `localhost` (when running locally) or `postgres_db` (inside Docker)
- Port: `5432`

## First-Time Setup

### Step 1: Initialize the Database Volume

Run this command once to create the Postgres container and initialize logical databases:

```bash
cd /path/to/MedStream
docker compose down -v
```

This removes any existing volume, ensuring the init script runs fresh on the next start.

### Step 2: Build and Start All Services

```bash
docker compose up --build
```

**What happens:**
1. Docker pulls the Postgres Alpine image.
2. Docker builds all six FastAPI service images.
3. Postgres starts and runs init-db.sql:
   - Creates three logical databases.
   - Creates `dev_user` with password `dev_password`.
   - Grants all privileges on each database to `dev_user`.
4. Each service container starts and connects to its assigned database via `DATABASE_URL` environment variable.
5. API Gateway (nginx) starts and listens on `http://localhost:8080`.

**First startup takes 30–60 seconds.** Subsequent startups are faster due to Docker layer caching.

### Step 3: Verify Everything Is Running

Check container status:
```bash
docker compose ps
```

Expected output: All containers `Up` and healthy.

Check that logical databases were created:
```bash
docker compose exec -T postgres_db psql -U admin -d postgres -tAc \
  "SELECT datname FROM pg_database WHERE datname IN ('medstream_auth','medstream_clinic','medstream_payments') ORDER BY datname;"
```

Expected output:
```
medstream_auth
medstream_clinic
medstream_payments
```

### Step 4: Test Service Health

Each service exposes a `GET /health` endpoint. Test via the API gateway:

```bash
curl http://localhost:8080/auth/health
curl http://localhost:8080/patients/health
curl http://localhost:8080/clinics/health
curl http://localhost:8080/appointments/health
curl http://localhost:8080/payments/health
curl http://localhost:8080/notifications/health
```

Expected response (example):
```json
{"status":"ok","service":"auth-service"}
```

### Step 5: Connect to a Database Directly (Optional)

If you need to query a database directly during development:

```bash
docker compose exec postgres_db psql -U dev_user -d medstream_auth
```

Then run SQL:
```sql
\dt  -- list tables
SELECT * FROM some_table;
```

Exit with `\q`.

## Daily Workflow

### Starting Work

```bash
cd /path/to/MedStream
docker compose up
```

The `-d` flag runs containers in the background:
```bash
docker compose up -d
```

### Stopping Work

Stop and remove containers (data persists in the volume):
```bash
docker compose down
```

Stop and **wipe the database volume** (runs init-db.sql again on next start):
```bash
docker compose down -v
```

### Viewing Logs

View logs for a specific service:
```bash
docker compose logs auth-service
docker compose logs -f auth-service  # follow tail
```

View logs for postgres:
```bash
docker compose logs postgres_db
```

## Database Connection Details

### Within Docker (Container-to-Container)

Each service's `DATABASE_URL` environment variable is set in docker-compose.yml:

- **auth-service**: `postgresql+psycopg2://dev_user:dev_password@postgres_db:5432/medstream_auth`
- **clinic-service**: `postgresql+psycopg2://dev_user:dev_password@postgres_db:5432/medstream_clinic`
- **appointment-service**: `postgresql+psycopg2://dev_user:dev_password@postgres_db:5432/medstream_clinic`
- **patient-service**: `postgresql+psycopg2://dev_user:dev_password@postgres_db:5432/medstream_clinic`
- **payment-service**: `postgresql+psycopg2://dev_user:dev_password@postgres_db:5432/medstream_payments`
- **notification-service**: `postgresql+psycopg2://dev_user:dev_password@postgres_db:5432/medstream_clinic`

### From Your Mac (Direct Connection)

Each service's `app/database.py` defines a default local URL if `DATABASE_URL` is not set:

```python
DEFAULT_DATABASE_URL = "postgresql+psycopg2://dev_user:dev_password@localhost:5432/medstream_auth"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
```

So if you run a service locally (outside Docker), it connects to `localhost:5432` with `dev_user`.

## Overriding DATABASE_URL for Azure

When deploying to Azure or any external database, set the `DATABASE_URL` environment variable before starting the service:

```bash
export DATABASE_URL="postgresql+psycopg2://azure_user:azure_password@azure-db-host:5432/medstream_auth"
docker compose up
```

Or set it in a `.env` file:
```
# .env (in project root)
DATABASE_URL=postgresql+psycopg2://azure_user:azure_password@azure-db-host:5432/medstream_auth
```

Docker Compose will automatically read and apply values from `.env`.

## Important Notes

### Volume Persistence

- The Postgres volume (`postgres_data`) is persisted on your Mac in Docker's storage.
- Data survives `docker compose down` but is **wiped** by `docker compose down -v`.
- Use `down -v` **only** when you want to reinitialize the database schema from `init-db.sql`.

### Init Script Only Runs Once

The init-db.sql script executes only on **first Postgres container startup** (when the volume is empty).

If you need to **re-run the init script:**
```bash
docker compose down -v
docker compose up --build
```

### Updating Service Code

If you modify a service's Python code, rebuild its image:
```bash
docker compose up --build
```

Or rebuild a single service:
```bash
docker compose build auth-service
docker compose up
```

### Troubleshooting

**Service stuck `Starting`:**
```bash
docker compose logs <service-name>
```

**Connection refused to postgres:**
```bash
docker compose exec postgres_db pg_isready -U admin
```

**Volume not cleaned between runs:**
```bash
docker volume ls
docker volume rm medstream_postgres_data
docker compose up --build
```

## Team Coordination

- **Each developer runs `docker compose up --build` locally** — no shared server needed.
- **Database schema changes** → update init-db.sql, then all devs run `docker compose down -v && docker compose up --build`.
- **Service-specific changes** → edit the service code, then `docker compose up --build`.
- **API Gateway routes** → defined in nginx.conf. Changes require container restart.

## Next Steps

- Start developing in your service's `app/routers/` folder.
- Use SQLAlchemy models in `app/models/` and Pydantic schemas in `app/schemas/`.
- Test endpoints via the gateway on `http://localhost:8080/<service-path>`.

Welcome to the team! 🚀
```

**Quick Summary for Your Team:**

1. **Clone the repo** and navigate to the MedStream folder.
2. **Run once:** `docker compose down -v`
3. **Then run:** `docker compose up --build`
4. **Wait 30–60 seconds** for everything to start.
5. **Test:** `curl http://localhost:8080/auth/health`
6. **To stop:** `docker compose down` (data stays) or `docker compose down -v` (wipe database).

That's it—every developer gets three isolated logical databases with the same credentials automatically.**Quick Summary for Your Team:**

1. **Clone the repo** and navigate to the MedStream folder.
2. **Run once:** `docker compose down -v`
3. **Then run:** `docker compose up --build`
4. **Wait 30–60 seconds** for everything to start.
5. **Test:** `curl http://localhost:8080/auth/health`
6. **To stop:** `docker compose down` (data stays) or `docker compose down -v` (wipe database).

