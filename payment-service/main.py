import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


cors_allow_origins = [
    origin.strip()
    for origin in os.getenv(
        "PAYMENT_SERVICE_CORS_ALLOW_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
cors_allow_credentials = _env_bool("PAYMENT_SERVICE_CORS_ALLOW_CREDENTIALS", True)

app = FastAPI(title="payment-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "payment-service"}
