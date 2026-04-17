from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@notification-db:5432/medstream_communication"
    # Security
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_SECRET: Optional[str] = None
    ALGORITHM: str = "HS256"
    
    SMTP_HOST: str = "smtp.mailtrap.io"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = "noreply@medstream.com"
    AUTH_SERVICE_URL: str = "http://auth-service:8000"
    
    ENVIRONMENT: str = "development"
    SERVICE_NAME: str = "notification-service"
    SERVICE_PORT: int = 8000
    CORS_ALLOW_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # SMS Settings
    TEXT_LK_API_URL: str = "https://app.text.lk/api/v3/sms/send"
    TEXT_LK_API_TOKEN: Optional[str] = "4305|BH7LMlUnffx5ubWzlASjKAPlZr4EMLmvc8toxzjU3ff572be"
    TEXT_LK_SENDER_ID: str = "TextLKDemo"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOW_ORIGINS.split(",") if origin.strip()]

settings = Settings()
