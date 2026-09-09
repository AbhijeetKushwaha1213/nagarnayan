"""
Application configuration via Pydantic Settings.

All values are read from environment variables (or a .env file).
No database connection is established here — DATABASE_URL is declared
but intentionally unused until the database phase.
"""

from __future__ import annotations

from typing import List

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
    APP_PORT: int = 8000
    APP_VERSION: str = "0.1.0"

    # ── Database (declared for future integration — not used in Phase 1) ───────
    DATABASE_URL: str = ""               # e.g. postgresql+asyncpg://user:pass@host/db

    # ── CORS ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> List[str]:
        """Allow CORS_ORIGINS to be provided as a comma-separated string."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value  # type: ignore[return-value]

    # ── Logging ────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"


# Module-level singleton — import this everywhere instead of re-instantiating.
settings = Settings()
