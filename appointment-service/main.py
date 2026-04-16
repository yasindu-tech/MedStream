from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers.internal import router as internal_router
from app.routers.search import router as search_router
from app.routers.booking import router as booking_router
from app.routers.followup import router as followup_router
from app.routers.reschedule import router as reschedule_router

app = FastAPI(title="appointment-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Internal: no auth, service-to-service only (doctor-service calls this)
app.include_router(internal_router, prefix="/internal")

# Public: JWT required, exposed via nginx at /appointments/doctors/search
app.include_router(search_router)

# Public: JWT required, exposed via nginx at /appointments/appointments/book
app.include_router(booking_router)

# Public: JWT required, exposed via nginx at /appointments/appointments/follow-ups
app.include_router(followup_router)

# Public: JWT required, exposed via nginx at /appointments/appointments/{id}/reschedule
app.include_router(reschedule_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "appointment-service"}
