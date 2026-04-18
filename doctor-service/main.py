import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import router as internal_router
from app.routers.public import router as public_router

app = FastAPI(title="doctor-service", version="0.1.0")

cors_allow_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
cors_allow_credentials = (
    os.getenv("CORS_ALLOW_CREDENTIALS", "true").strip().lower() == "true"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(internal_router, prefix="/internal")
app.include_router(public_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "doctor-service"}
