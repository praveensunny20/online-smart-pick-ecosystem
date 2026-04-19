"""
Application configuration module.

Loads environment variables from .env file using pydantic-settings.
All config is accessed through the `settings` singleton at the bottom of this file.
"""
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    pydantic-settings automatically reads from .env file and OS environment.
    Type annotations provide automatic type coercion and validation.
    """

    # Tells pydantic-settings where to find the .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra env vars that aren't defined here
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

    # CORS - stored as string, parsed to list
    CORS_ORIGINS: str = "http://localhost:3000"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"

    # Frontend URL
    FRONTEND_URL: str = "http://localhost:3000"

    # Seed data
    SEED_AGENCY_NAME: str = "Demo Marketing Agency"
    SEED_ADMIN_EMAIL: str = "admin@onlinesmartpick.com"
    SEED_ADMIN_PASSWORD: str = "ChangeMe123!"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_url(cls, v: str, info) -> str:
        """
        Build DATABASE_URL from component parts if it wasn't explicitly set.
        We use asyncpg driver for async SQLAlchemy.
        """
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
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def sync_database_url(self) -> str:
        """
        Synchronous database URL (for Alembic migrations and init scripts).
        Alembic uses psycopg2 (sync), not asyncpg.
        """
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    @lru_cache ensures we only parse env vars once per process.
    """
    return Settings()


# Singleton instance used throughout the app
settings = get_settings()
