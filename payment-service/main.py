from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import payments_router, refunds_router, summaries_router
from app.routers.internal import router as internal_router
from app.config import settings
from decimal import Decimal
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # P1.1 Use create_all to ensure models (source of truth) are reflected in DB
    async with engine.begin() as conn:
        # We assume types like payment_status are pre-created, so we catch 
        # potential errors if they attempt to redefine them but models logic 
        # uses create_type=False to avoid this.
        await conn.run_sync(Base.metadata.create_all)
    
    # Verify split percentages sum to 100.0 (P4.1)
    total = (Decimal(str(settings.PLATFORM_COMMISSION_PCT)) +
             Decimal(str(settings.CLINIC_SHARE_PCT)) +
             Decimal(str(settings.DOCTOR_SHARE_PCT)))
    if total != Decimal("100.0"):
        logger.warning(
            f"Split percentages sum to {total}, not 100.0. "
            f"Check PLATFORM_COMMISSION_PCT, CLINIC_SHARE_PCT, DOCTOR_SHARE_PCT."
        )
    
    logger.info(f"{settings.SERVICE_NAME} started on port {settings.SERVICE_PORT}")
    yield
    # Cleanup
    await engine.dispose()

app = FastAPI(
    title="MedStream Payment Service", 
    version="1.0.0", 
    lifespan=lifespan
)

# CORS (P1.7)
app.add_middleware(
    CORSMiddleware, 
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"]
)

# Router Mounting (P1.7)
app.include_router(payments_router,  prefix="/api/payments", tags=["payments"])
app.include_router(refunds_router,   prefix="/api/payments", tags=["refunds"])
app.include_router(summaries_router, prefix="/api/payments", tags=["summaries"])
app.include_router(internal_router, prefix="/internal")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME}
