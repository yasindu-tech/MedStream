from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import router as clinics_router
from app.routers.dashboard import router as dashboard_router
from app.routers.doctor_assignments import router as doctor_assignments_router
from app.routers.internal import router as internal_router
from app.routers.staff import router as staff_router

import app.models  # noqa: F401

Base.metadata.create_all(bind=engine)

app = FastAPI(title="clinic-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clinics_router)
app.include_router(staff_router)
app.include_router(doctor_assignments_router)
app.include_router(dashboard_router)

app.include_router(internal_router, prefix="/internal")



@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "clinic-service"}
