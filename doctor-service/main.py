from fastapi import FastAPI
from app.routers import router as internal_router

app = FastAPI(title="doctor-service", version="0.1.0")

app.include_router(internal_router, prefix="/internal")


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "doctor-service"}
