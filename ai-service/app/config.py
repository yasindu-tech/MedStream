from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DOCTOR_SERVICE_URL: str = "http://doctor-service:8000"
    APPOINTMENT_SERVICE_URL: str = "http://appointment-service:8000"
    PATIENT_SERVICE_URL: str = "http://patient-service:8000"
    INTERNAL_SERVICE_TOKEN: str = "medstream-internal-token"
    CHATBOT_ENABLE_LLM: str = "true"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-latest"
    OVERVIEW_RECENT_LIMIT: int = 10
    OVERVIEW_HTTP_TIMEOUT_SECONDS: float = 20.0
    REPORT_FETCH_TIMEOUT_SECONDS: float = 5.0
    REPORT_TEXT_MAX_CHARS: int = 2400
    POST_CONSULTATION_ENABLE_LLM: str = "true"
    POST_CONSULTATION_HTTP_TIMEOUT_SECONDS: float = 20.0
    POST_CONSULTATION_MAX_NOTES_CHARS: int = 1200

    class Config:
        env_file = ".env"

    @property
    def chatbot_enable_llm(self) -> bool:
        return self.CHATBOT_ENABLE_LLM.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @property
    def post_consultation_enable_llm(self) -> bool:
        return self.POST_CONSULTATION_ENABLE_LLM.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }


settings = Settings()
