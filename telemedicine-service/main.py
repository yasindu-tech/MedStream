from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.internal import router as internal_router
from app.routers.oauth import router as oauth_router
from app.routers.sessions import router as sessions_router

app = FastAPI(title="telemedicine-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(internal_router, prefix="/internal")
app.include_router(sessions_router)
app.include_router(oauth_router)



@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "telemedicine-service"}
