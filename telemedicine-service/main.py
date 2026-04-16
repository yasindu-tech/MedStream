import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.internal import router as internal_router

app = FastAPI(title="telemedicine-service", version="0.1.0")

cors_allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
cors_allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(internal_router, prefix="/internal")



@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "telemedicine-service"}
