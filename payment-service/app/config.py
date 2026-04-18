from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from decimal import Decimal

class Settings(BaseSettings):
    # Core Service Settings
    SERVICE_NAME: str = "payment-service"
    SERVICE_PORT: int = 8000
    ENVIRONMENT: str = "development"

    # Database Settings
    # postgresql+asyncpg://postgres:password@finance-db:5432/medstream_finance
    DATABASE_URL: str

    # JWT Settings
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    # Commission / Split Settings
    PLATFORM_COMMISSION_PCT: float = 10.0
    CLINIC_SHARE_PCT: float = 60.0
    DOCTOR_SHARE_PCT: float = 30.0

    # Notification Service
    NOTIFICATION_SERVICE_URL: str = "http://notification-service:8000"

    # Appointment Service (for payment status callbacks)
    APPOINTMENT_SERVICE_URL: str = "http://appointment-service:8000"

    # Internal token for service-to-service calls
    INTERNAL_SERVICE_TOKEN: str = "medstream-internal-token"

    # Doctor Service (to resolve user_id to doctor_id)
    DOCTOR_SERVICE_URL: str = "http://doctor-service:8000"

    # Clinic Service (to resolve user_id to clinic_id)
    CLINIC_SERVICE_URL: str = "http://clinic-service:8000"

    # Stripe Settings
    STRIPE_API_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_SUCCESS_URL: str = "http://localhost:3000/payment/success?session_id={CHECKOUT_SESSION_ID}"
    STRIPE_CANCEL_URL: str = "http://localhost:3000/payment/cancel"
    ENABLE_STRIPE_MOCK: bool = True

    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
