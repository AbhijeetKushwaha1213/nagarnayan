"""
Tests for GET /api/v1/health
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Return a synchronous test client for the FastAPI app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for the /api/v1/health route."""

    def test_health_status_code(self, client: TestClient) -> None:
        """Health endpoint must return HTTP 200."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_response_shape(self, client: TestClient) -> None:
        """Response body must contain 'status', 'service', and 'database' keys."""
        response = client.get("/api/v1/health")
        body = response.json()
        assert "status" in body
        assert "service" in body
        assert "database" in body

    def test_health_status_value(self, client: TestClient) -> None:
        """'status' must be 'healthy' (DB not configured → not_configured, still healthy)."""
        response = client.get("/api/v1/health")
        assert response.json()["status"] in ("healthy", "degraded")

    def test_health_service_value(self, client: TestClient) -> None:
        """'service' field must identify the backend."""
        response = client.get("/api/v1/health")
        assert response.json()["service"] == "nagar-nayan-backend"

    def test_health_content_type(self, client: TestClient) -> None:
        """Response must be JSON."""
        response = client.get("/api/v1/health")
        assert "application/json" in response.headers["content-type"]

    def test_health_database_key(self, client: TestClient) -> None:
        """'database' sub-object must have a 'status' field."""
        response = client.get("/api/v1/health")
        db = response.json()["database"]
        assert "status" in db
        assert db["status"] in ("healthy", "unhealthy", "not_configured")

    def test_health_no_db_configured(self, client: TestClient) -> None:
        """When DATABASE_URL is empty, overall status is still 'healthy'."""
        import os

        if os.environ.get("DATABASE_URL"):
            pytest.skip("DATABASE_URL is set — DB tests should check differently")
        response = client.get("/api/v1/health")
        body = response.json()
        assert body["status"] == "healthy"
        assert body["database"]["status"] == "not_configured"


# ---------------------------------------------------------------------------
# Root endpoint tests
# ---------------------------------------------------------------------------


class TestRootEndpoint:
    """Tests for the root / route."""

    def test_root_status_code(self, client: TestClient) -> None:
        """Root endpoint must return HTTP 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_contains_service_name(self, client: TestClient) -> None:
        """Root response must include the service name."""
        response = client.get("/")
        assert "service" in response.json()

    def test_root_api_prefix(self, client: TestClient) -> None:
        """Root response must expose the API prefix."""
        response = client.get("/")
        assert response.json().get("api_prefix") == "/api/v1"


# ---------------------------------------------------------------------------
# Database Connectivity Probe Unit Tests
# ---------------------------------------------------------------------------


class TestDatabaseHealthCheckProbe:
    """Direct tests for check_db_connection and health degradation."""

    @pytest.mark.asyncio
    async def test_check_db_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.config import settings
        from app.core.database import check_db_connection

        monkeypatch.setattr(settings, "DATABASE_URL", "")
        status, detail = await check_db_connection()
        assert status == "not_configured"
        assert "not set" in detail

    @pytest.mark.asyncio
    async def test_check_db_healthy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import AsyncMock, MagicMock
        from app.core.config import settings
        import app.core.database as db_mod

        monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=None)

        monkeypatch.setattr(db_mod, "_get_engine", lambda: mock_engine)

        status, detail = await db_mod.check_db_connection()
        assert status == "healthy"
        assert detail == "OK"

    @pytest.mark.asyncio
    async def test_check_db_unhealthy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import AsyncMock, MagicMock
        from app.core.config import settings
        import app.core.database as db_mod

        monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")

        mock_engine = MagicMock()
        mock_engine.connect.side_effect = ConnectionRefusedError("Connection refused")
        monkeypatch.setattr(db_mod, "_get_engine", lambda: mock_engine)

        status, detail = await db_mod.check_db_connection()
        assert status == "unhealthy"
        assert detail == "ConnectionRefusedError"

    def test_health_endpoint_degraded_when_db_unhealthy(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import AsyncMock
        import app.api.routes.health as health_route

        monkeypatch.setattr(
            health_route,
            "check_db_connection",
            AsyncMock(return_value=("unhealthy", "ConnectionRefusedError")),
        )

        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["database"]["status"] == "unhealthy"
        assert body["database"]["detail"] == "ConnectionRefusedError"

