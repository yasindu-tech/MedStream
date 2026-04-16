import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
cors_allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

app = FastAPI(title="clinic-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "clinic-service"}
