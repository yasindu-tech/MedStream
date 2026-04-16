import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _get_allowed_origins() -> list[str]:
    origins = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


def _get_allow_credentials() -> bool:
    return os.getenv("CORS_ALLOW_CREDENTIALS", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


app = FastAPI(title="notification-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=_get_allow_credentials(),
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "notification-service"}
