from fastapi import FastAPI

app = FastAPI(title="notification-service", version="0.1.0")


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "notification-service"}
