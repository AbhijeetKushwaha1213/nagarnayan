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
        """Response body must contain 'status' and 'service' keys."""
        response = client.get("/api/v1/health")
        body = response.json()
        assert "status" in body
        assert "service" in body

    def test_health_status_value(self, client: TestClient) -> None:
        """'status' field must equal 'healthy'."""
        response = client.get("/api/v1/health")
        assert response.json()["status"] == "healthy"

    def test_health_service_value(self, client: TestClient) -> None:
        """'service' field must identify the backend."""
        response = client.get("/api/v1/health")
        assert response.json()["service"] == "nagar-nayan-backend"

    def test_health_content_type(self, client: TestClient) -> None:
        """Response must be JSON."""
        response = client.get("/api/v1/health")
        assert "application/json" in response.headers["content-type"]


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
