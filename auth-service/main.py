from fastapi import FastAPI
from app.database import Base, engine
from app.routers import router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MedStream Auth Service", version="1.0.0")
app.include_router(router)

@app.get("/health")
def health():
    return {"status": "ok"}

