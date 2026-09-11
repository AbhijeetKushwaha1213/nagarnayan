"""
Shared pytest fixtures and configuration for Nagar Nayan backend tests.

Test Strategy:
  - Phase 1 tests (test_health.py):  use synchronous TestClient, no DB needed.
  - Phase 2 DB tests:                use synchronous TestClient with requires_db marker;
                                     skipped unless DATABASE_URL is set and asyncpg
                                     is importable.

To run Phase 2 DB tests:
    docker compose up -d db
    export DATABASE_URL=postgresql+asyncpg://nagarnayan:secret@localhost:5432/nagar_nayan
    alembic upgrade head
    pytest -v
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ── Environment checks ────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "")
HAS_DATABASE_URL = bool(DATABASE_URL)

try:
    import asyncpg  # noqa: F401

    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

DB_AVAILABLE = HAS_DATABASE_URL and HAS_ASYNCPG

# ── Custom markers ────────────────────────────────────────────────────────────

requires_db = pytest.mark.skipif(
    not DB_AVAILABLE,
    reason=(
        "DB tests require DATABASE_URL env var and asyncpg. "
        "Run: docker compose up -d db && "
        "export DATABASE_URL=postgresql+asyncpg://nagarnayan:secret@localhost:5432/nagar_nayan && "
        "alembic upgrade head"
    ),
)

# ── Shared fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Synchronous FastAPI test client — works for all tests."""
    return TestClient(app, raise_server_exceptions=True)
