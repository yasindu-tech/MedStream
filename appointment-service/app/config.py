from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://dev_user:dev_password@localhost:5434/medstream_patientcare"
    DOCTOR_SERVICE_URL: str = "http://doctor-service:8000"
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"


settings = Settings()
