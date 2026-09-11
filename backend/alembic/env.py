"""
Alembic environment configuration — Phase 2.

Uses the synchronous psycopg2 driver for migrations (Alembic doesn't support
async natively). The app itself uses asyncpg at runtime.
"""

from __future__ import annotations

import os
import re
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

load_dotenv()

# ── Alembic Config ────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import models so metadata is populated ────────────────────────────────────
# This is the critical import — it causes every model module to execute,
# registering all tables on Base.metadata.
import app.models  # noqa: F401, E402
from app.core.database import Base  # noqa: E402

target_metadata = Base.metadata


# ── URL helpers ───────────────────────────────────────────────────────────────

def _get_sync_url() -> str:
    """
    Get a synchronous (psycopg2) database URL for Alembic.

    Converts the async asyncpg URL to a sync psycopg2 URL.
    Falls back to the alembic.ini sqlalchemy.url if DATABASE_URL is not set.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        url = config.get_main_option("sqlalchemy.url", "")

    # Replace async driver scheme with sync driver scheme
    url = re.sub(r"^postgresql\+asyncpg://", "postgresql+psycopg2://", url)
    return url


# ── Migration runners ─────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL script)."""
    url = _get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        url = config.get_main_option("sqlalchemy.url", "")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    try:
        import psycopg2  # noqa: F401
        cfg = config.get_section(config.config_ini_section) or {}
        cfg["sqlalchemy.url"] = _get_sync_url()

        connectable = engine_from_config(
            cfg,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            do_run_migrations(connection)
    except ImportError:
        import asyncio
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
