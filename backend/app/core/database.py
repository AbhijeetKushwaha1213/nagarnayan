"""
Database engine, session factory, declarative Base, and FastAPI dependency.

All models import Base from here. The engine is created lazily so the app can
start and serve Phase 1 endpoints even if DATABASE_URL is not set.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Declarative Base ─────────────────────────────────────────────────────────
# All SQLAlchemy models inherit from this single Base so that
# Base.metadata contains every table and Alembic can discover them.


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# ── Engine & Session Factory ─────────────────────────────────────────────────
# Created lazily so the app starts cleanly even without DATABASE_URL.

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine | None:
    """Return the shared async engine, creating it once on first call."""
    global _engine
    if _engine is None and settings.DATABASE_URL:
        url = settings.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        _engine = create_async_engine(
            url,
            echo=False,
            pool_pre_ping=True,   # verify connections before use
            pool_size=5,
            max_overflow=10,
        )
        logger.info("Async database engine created")
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    """Return the shared session factory, creating it once on first call."""
    global _session_factory
    if _session_factory is None:
        engine = _get_engine()
        if engine is not None:
            _session_factory = async_sessionmaker(
                engine,
                expire_on_commit=False,
                class_=AsyncSession,
            )
    return _session_factory


# ── FastAPI Dependency ────────────────────────────────────────────────────────


async def get_db() -> AsyncIterator[AsyncSession]:
    """
    FastAPI dependency that yields an AsyncSession per request.

    Usage in route:
        async def my_route(session: AsyncSession = Depends(get_db)):
            ...
    """
    factory = _get_session_factory()
    if factory is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="Database not configured. Set DATABASE_URL environment variable.",
        )
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# ── Health Probe ─────────────────────────────────────────────────────────────


async def check_db_connection() -> tuple[str, str]:
    """
    Probe the database and return a (status, detail) tuple.

    Returns:
        ("healthy", "OK")              — connected successfully
        ("unhealthy", "<error type>")  — connected but query failed
        ("not_configured", "...")      — DATABASE_URL is empty
    """
    if not settings.DATABASE_URL:
        return "not_configured", "DATABASE_URL not set"

    try:
        engine = _get_engine()
        if engine is None:
            return "not_configured", "Engine not initialised"

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "healthy", "OK"
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        return "unhealthy", type(exc).__name__
