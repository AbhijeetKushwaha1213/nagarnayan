"""
Application configuration via Pydantic Settings.

All values are read from environment variables (or a .env file).
"""

from __future__ import annotations

from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Nagar Nayan backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    APP_NAME: str = "Nagar Nayan Backend"
    APP_ENV: str = "development"         # development | staging | production
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8080
    APP_VERSION: str = "0.2.0"

    # ── Database ───────────────────────────────────────────────────────────────
    # Full async DSN used by the application (asyncpg driver).
    # e.g. postgresql+asyncpg://user:pass@host:5432/dbname
    DATABASE_URL: str = ""

    # Individual credentials — used by docker-compose; the app always reads
    # the assembled DATABASE_URL above.
    POSTGRES_USER: str = "nagarnayan"
    POSTGRES_PASSWORD: str = "secret"
    POSTGRES_DB: str = "nagar_nayan"

    # ── CORS ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> List[str]:
        """Allow CORS_ORIGINS to be provided as a comma-separated string or list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, (list, tuple)):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return []

    # ── Event Correlation & Deduplication ──────────────────────────────────────
    EVENT_CORRELATION_RADIUS_METERS: float = 50.0
    EVENT_CORRELATION_WINDOW_SECONDS: int = 300
    EVENT_DEDUP_RADIUS_METERS: float = 50.0
    EVENT_DEDUP_TIME_WINDOW_SECONDS: int = 300

    # ── Severity & Alert Engine ────────────────────────────────────────────────
    ALERT_MEDIUM_THRESHOLD_DETECTION_COUNT: int = 3
    ALERT_MEDIUM_THRESHOLD_DISTINCT_BUSES: int = 2
    ALERT_MEDIUM_THRESHOLD_PERSISTENCE_SECONDS: int = 120

    # ── Logging ────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"


# Module-level singleton — import this everywhere instead of re-instantiating.
settings = Settings()
