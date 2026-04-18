from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import events, inbox, templates, preferences, contact
from app.services.notification_service import seed_default_templates, process_notification_queue
from app.services.websocket_service import manager
from app.middleware import get_current_user
from app.config import settings
import logging
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables if they don't exist and seed default templates
    logger.info(f"Starting {settings.SERVICE_NAME}...")
    async with engine.begin() as conn:
        # Note: In production with multiple schemas, we ensure the schema exists first.
        # But for this project, the init SQL handles schema creation.
        await conn.run_sync(Base.metadata.create_all)
    
    await seed_default_templates()
    
    # Start background worker
    async def worker_loop():
        while True:
            try:
                await process_notification_queue()
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
            await asyncio.sleep(30)  # Check queue every 30 seconds

    asyncio.create_task(worker_loop())
    
    logger.info(f"{settings.SERVICE_NAME} started on port {settings.SERVICE_PORT}")
    yield
    # Shutdown
    logger.info(f"Shutting down {settings.SERVICE_NAME}...")
    await engine.dispose()

app = FastAPI(
    title="MedStream Notification Service",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# Include routers
app.include_router(events.router,      prefix="/api/notifications", tags=["events"])
app.include_router(inbox.router,       prefix="/api/notifications", tags=["inbox"])
app.include_router(templates.router,   prefix="/api/notifications", tags=["templates"])
app.include_router(preferences.router, prefix="/api/notifications", tags=["preferences"])
app.include_router(contact.router,     prefix="/api/notifications", tags=["contact"])

@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME}

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket, user_id)
