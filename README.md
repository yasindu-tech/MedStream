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

1. Build and start all services:

	docker compose up --build

2. Access the API gateway:

	http://localhost:8080

3. Check service health through the API gateway:

	curl http://localhost:8080/auth/health
	curl http://localhost:8080/patients/health
	curl http://localhost:8080/clinics/health
	curl http://localhost:8080/appointments/health
	curl http://localhost:8080/payments/health
	curl http://localhost:8080/notifications/health

4. Optional direct service health checks (without gateway):

	curl http://localhost:8001/health
	curl http://localhost:8002/health
	curl http://localhost:8003/health
	curl http://localhost:8004/health
	curl http://localhost:8005/health
	curl http://localhost:8006/health

5. Stop everything:

	docker compose down

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