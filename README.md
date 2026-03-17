# MedStream

MedStream is a microservices workspace scaffolded for FastAPI services with local Docker Compose orchestration and Kubernetes/Azure deployment placeholders.

## Services

- auth-service
- patient-service
- clinic-service
- appointment-service
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
	curl http://localhost:8080/payments/health
	curl http://localhost:8080/notifications/health

5. Optional direct service health checks (without gateway):

	curl http://localhost:8001/health
	curl http://localhost:8002/health
	curl http://localhost:8003/health
	curl http://localhost:8004/health
	curl http://localhost:8005/health
	curl http://localhost:8006/health

6. Stop everything:

	docker compose down

## Local Logical Databases

Postgres is started as postgres_db, and it runs [infrastructure/db/init-db.sql](infrastructure/db/init-db.sql) on first container initialization.

It creates:

- medstream_auth
- medstream_clinic
- medstream_payments
- dev_user / dev_password

Important:

- The init SQL script runs only when the Postgres volume is empty.
- Use docker compose down -v to wipe the volume and rerun the initialization script.

Service DATABASE_URL mapping in compose:

- auth-service -> medstream_auth
- clinic-service -> medstream_clinic
- appointment-service -> medstream_clinic
- patient-service -> medstream_clinic
- payment-service -> medstream_payments
- notification-service -> medstream_clinic

Each service reads DATABASE_URL from environment (see app/database.py in each service), so you can override it for Azure or any external DB.

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
- /payments/health -> payment-service
- /notifications/health -> notification-service

## Infrastructure and CI/CD

- API Gateway config: api-gateway/nginx.conf
- Kubernetes ingress: infrastructure/k8s/ingress-routes.yaml
- Azure workflow placeholder: .github/workflows/azure-deploy.yml