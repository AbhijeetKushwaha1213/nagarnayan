"""Core package: configuration and logging."""

from app.core.config import Settings, settings
from app.core.logging import setup_logging

__all__ = ["Settings", "settings", "setup_logging"]
