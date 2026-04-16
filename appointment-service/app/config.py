from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://dev_user:dev_password@localhost:5434/medstream_patientcare"
    DOCTOR_SERVICE_URL: str = "http://doctor-service:8000"
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    RESCHEDULE_WINDOW_HOURS: int = 24
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    CORS_ALLOW_CREDENTIALS: str = "true"

    class Config:
        env_file = ".env"

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def cors_allow_credentials(self) -> bool:
        return self.CORS_ALLOW_CREDENTIALS.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }


settings = Settings()
