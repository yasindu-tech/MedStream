# MedStream

MedStream is a microservices workspace scaffolded for FastAPI services with local Docker Compose orchestration and Kubernetes/Azure deployment placeholders.

## Services

- auth-service
- patient-service
- clinic-service
- appointment-service
- doctor-service
- telemedicine-service
- payment-service
- notification-service

Each service includes:

- app/ (routers, models, schemas, database.py)
- main.py
- requirements.txt
- Dockerfile

## Run Locally

1. First-time setup (or reinitialize databases):

	docker compose down -v

2. Build and start all services:

	docker compose up --build

3. Access the API gateway:

	http://localhost:8080

4. Check service health through the API gateway:

	curl http://localhost:8080/auth/health
	curl http://localhost:8080/patients/health
	curl http://localhost:8080/clinics/health
	curl http://localhost:8080/appointments/health
	curl http://localhost:8080/doctors/health
	curl http://localhost:8080/telemedicine/health
	curl http://localhost:8080/payments/health
	curl http://localhost:8080/notifications/health

5. Optional direct service health checks (without gateway):

	curl http://localhost:8001/health
	curl http://localhost:8002/health
	curl http://localhost:8003/health
	curl http://localhost:8004/health
	curl http://localhost:8007/health
	curl http://localhost:8008/health
	curl http://localhost:8005/health
	curl http://localhost:8006/health

6. Stop everything:

	docker compose down

## Separate PostgreSQL Databases

This setup uses five separate Postgres containers (not logical databases in one server):

- AuthDB: medstream_auth on auth_db (host port 5432)
- AdminDB: medstream_admin on admin_db (host port 5433)
- PatientCareDB: medstream_patientcare on patientcare_db (host port 5434)
- FinanceDB: medstream_finance on finance_db (host port 5435)
- CommunicationDB: medstream_communication on communication_db (host port 5436)

Initialization scripts:

- [infrastructure/db/init-db.sql](infrastructure/db/init-db.sql) (AuthDB)
- [infrastructure/db/init-admin-db.sql](infrastructure/db/init-admin-db.sql)
- [infrastructure/db/init-patientcare-db.sql](infrastructure/db/init-patientcare-db.sql)
- [infrastructure/db/init-finance-db.sql](infrastructure/db/init-finance-db.sql)
- [infrastructure/db/init-communication-db.sql](infrastructure/db/init-communication-db.sql)

Service DATABASE_URL mapping in compose:

- auth-service -> auth_db / medstream_auth
- clinic-service -> admin_db / medstream_admin
- patient-service -> patientcare_db / medstream_patientcare
- appointment-service -> patientcare_db / medstream_patientcare
- doctor-service -> admin_db / medstream_admin
- telemedicine-service -> patientcare_db / medstream_patientcare
- payment-service -> finance_db / medstream_finance
- notification-service -> communication_db / medstream_communication

Important:

- Init scripts run only when the respective DB volume is empty.
- Use docker compose down -v to reinitialize all five databases from scripts.

## Health Endpoints

Every service exposes the same endpoint:

- GET /health

Each response returns:

{
  "status": "ok",
  "service": "<service-name>"
}

Gateway paths map to each service health route:

- /auth/health -> auth-service
- /patients/health -> patient-service
- /clinics/health -> clinic-service
- /appointments/health -> appointment-service
- /doctors/health -> doctor-service
- /telemedicine/health -> telemedicine-service
- /payments/health -> payment-service
- /notifications/health -> notification-service

## Infrastructure and CI/CD

- API Gateway config: api-gateway/nginx.conf
- Kubernetes ingress: infrastructure/k8s/ingress-routes.yaml
- Azure workflow placeholder: .github/workflows/azure-deploy.yml