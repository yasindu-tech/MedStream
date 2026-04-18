from fastapi import FastAPI

from app.routers.internal import router as internal_router

app = FastAPI(title="ai-service", version="0.1.0")

# Internal-only endpoints for service-to-service calls.
app.include_router(internal_router, prefix="/internal")


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "ai-service"}
