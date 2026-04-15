from fastapi import FastAPI
from app.routers.internal import router as internal_router
from app.routers.search import router as search_router

app = FastAPI(title="appointment-service", version="0.1.0")

# Internal: no auth, service-to-service only (doctor-service calls this)
app.include_router(internal_router, prefix="/internal")

# Public: JWT required, exposed via nginx at /appointments/doctors/search
app.include_router(search_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "appointment-service"}
