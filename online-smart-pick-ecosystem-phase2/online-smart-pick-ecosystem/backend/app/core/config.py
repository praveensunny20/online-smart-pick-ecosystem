"""
Application configuration module.

Loads environment variables from .env file using pydantic-settings.
All config is accessed through the `settings` singleton at the bottom of this file.

Phase 2 additions:
    - Email (Resend) for signup verification & password reset
    - DATA_PROVIDER toggle (mock / windsor / supermetrics)
    - Rate limit settings
    - Sync retention window (how many days of history to pull)
"""
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Online Smart Pick Ecosystem"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security - JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email-verification + password-reset tokens (separate short-lived scope)
    EMAIL_VERIFY_TOKEN_EXPIRE_HOURS: int = 48
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 2

    # Encryption
    ENCRYPTION_KEY: str

    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = ""  # Built by validator below if empty

    # Redis / Celery
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"
    # Scheduler cron for nightly sync (Celery Beat cron format: minute, hour, day_of_week, ...)
    SYNC_SCHEDULE_HOUR_UTC: int = 3   # 3 AM UTC = 8:30 AM IST
    SYNC_SCHEDULE_MINUTE: int = 0
    # How many days of historical data each sync should pull
    SYNC_LOOKBACK_DAYS: int = 30

    # CORS - stored as string, parsed to list
    CORS_ORIGINS: str = "http://localhost:3000"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"

    # Frontend URL (used inside verification / reset emails)
    FRONTEND_URL: str = "http://localhost:3000"

    # Email (Resend). If RESEND_API_KEY is empty, emails are logged to console.
    RESEND_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = "noreply@onlinesmartpick.com"
    EMAIL_FROM_NAME: str = "Online Smart Pick"

    # Data provider for platform metrics
    # Options: "mock" (fixture data) | "windsor" (Phase 3) | "supermetrics" (Phase 3)
    DATA_PROVIDER: str = "mock"
    WINDSOR_API_KEY: str = ""
    SUPERMETRICS_API_KEY: str = ""

    # Rate limiting (slowapi) — applied per-IP
    RATE_LIMIT_LOGIN_PER_MINUTE: str = "10/minute"
    RATE_LIMIT_SIGNUP_PER_HOUR: str = "5/hour"
    RATE_LIMIT_DEFAULT: str = "120/minute"

    # Seed data
    SEED_AGENCY_NAME: str = "Demo Marketing Agency"
    SEED_ADMIN_EMAIL: str = "admin@onlinesmartpick.com"
    SEED_ADMIN_PASSWORD: str = "ChangeMe123!"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_url(cls, v: str, info) -> str:
        """Build DATABASE_URL from component parts if it wasn't explicitly set."""
        if v:
            return v
        values = info.data
        user = values.get("POSTGRES_USER", "smartpick")
        password = values.get("POSTGRES_PASSWORD", "smartpick")
        host = values.get("POSTGRES_HOST", "postgres")
        port = values.get("POSTGRES_PORT", 5432)
        db = values.get("POSTGRES_DB", "smartpick_db")
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse the comma-separated CORS_ORIGINS string into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def sync_database_url(self) -> str:
        """Synchronous database URL (for Alembic + Celery worker sync DB ops)."""
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
