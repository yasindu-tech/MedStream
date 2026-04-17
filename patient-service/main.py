import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.routers import router
from app.routers.internal import router as internal_router


def ensure_patient_schema() -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE patientcare.patients ADD COLUMN IF NOT EXISTS email varchar(255);"
        )
        conn.exec_driver_sql(
            "ALTER TABLE patientcare.patients ADD COLUMN IF NOT EXISTS profile_status varchar(30);"
        )
        conn.exec_driver_sql(
            "ALTER TABLE patientcare.patients ADD COLUMN IF NOT EXISTS emergency_contact varchar(255);"
        )
        conn.exec_driver_sql(
            "ALTER TABLE patientcare.patients ADD COLUMN IF NOT EXISTS profile_image_url text;"
        )
        conn.exec_driver_sql(
            "ALTER TABLE patientcare.patients ADD COLUMN IF NOT EXISTS pending_email varchar(255);"
        )
        conn.exec_driver_sql(
            "UPDATE patientcare.patients SET profile_status = 'active' WHERE profile_status IS NULL;"
        )
        conn.exec_driver_sql(
            "ALTER TABLE patientcare.patients ALTER COLUMN profile_status SET DEFAULT 'active';"
        )
        conn.exec_driver_sql(
            "ALTER TABLE patientcare.patients ALTER COLUMN profile_status SET NOT NULL;"
        )

Base.metadata.create_all(bind=engine)
ensure_patient_schema()

app = FastAPI(title="patient-service", version="0.1.0")

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

app.include_router(router)
app.include_router(internal_router, prefix="/internal")


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "patient-service"}
