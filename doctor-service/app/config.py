from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://dev_user:dev_password@localhost:5433/medstream_admin"
    APPOINTMENT_SERVICE_URL: str = "http://appointment-service:8000"
    NOTIFICATION_SERVICE_URL: str = "http://notification-service:8000"
    AUTH_SERVICE_URL: str = "http://auth-service:8000"

    class Config:
        env_file = ".env"


settings = Settings()
