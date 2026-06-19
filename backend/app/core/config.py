from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path

# Absolute path to backend/.env — works regardless of the process's CWD
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str
    SYNC_DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    FEEDBACK_TOKEN_EXPIRE_HOURS: int = 72
    GROQ_API_KEY: str
    GEMINI_API_KEY: Optional[str] = None
    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: str = "noreply@platform.com"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Bilvantis TIP"
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    FEEDBACK_THRESHOLD: int = 5
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    PGVECTOR_DIMENSION: int = 768
    APP_NAME: str = "Bilvantis Training Intelligence Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    class Config:
        env_file = str(_ENV_FILE)
        extra = "ignore"


def get_settings() -> Settings:
    return Settings()


settings = Settings()
