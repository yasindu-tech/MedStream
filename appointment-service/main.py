from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers.internal import router as internal_router
from app.routers.search import router as search_router
from app.routers.booking import router as booking_router
from app.routers.followup import router as followup_router
from app.routers.reschedule import router as reschedule_router
from app.routers.cancellation import router as cancellation_router
from app.routers.history import router as history_router
from app.routers.outcome import router as outcome_router
from app.routers.consultation import router as consultation_router
from app.routers.admin import router as admin_router
from app.routers.policy import router as policy_router

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

# Public: no JWT required, exposed via nginx at /appointments/doctors/search
app.include_router(search_router)

# Public: JWT required, exposed via nginx at /appointments/appointments/book
app.include_router(booking_router)

# Public: JWT required, exposed via nginx at /appointments/appointments/follow-ups
app.include_router(followup_router)

# Public: JWT required, exposed via nginx at /appointments/appointments/{id}/reschedule
app.include_router(reschedule_router)

# Public: JWT required, exposed via nginx at /appointments/appointments/{id}/cancel
app.include_router(cancellation_router)

# Public: JWT required, exposed via nginx at /appointments/appointments/{id}/accept
app.include_router(consultation_router)

# Public: JWT required, exposed via nginx at /appointments/appointments (GET)
app.include_router(history_router)

# Public: JWT required, appointment outcome actions.
app.include_router(outcome_router)

# Public: JWT required, admin and clinic-staff management endpoints.
app.include_router(admin_router)

# Public: JWT required, appointment policy management.
app.include_router(policy_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "appointment-service"}
