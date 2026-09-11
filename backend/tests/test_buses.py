"""
Tests for Bus CRUD API — /api/v1/buses

Requires DATABASE_URL and asyncpg. Skipped otherwise.
Run via: docker compose up -d db && alembic upgrade head && pytest -v
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from tests.conftest import requires_db

# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_BUS = {
    "bus_number": f"TEST-{uuid.uuid4().hex[:6].upper()}",
    "route_id": "ROUTE-TEST-1",
    "status": "active",
}


@pytest.fixture
def created_bus(client: TestClient) -> dict:
    """Create a bus and delete it after the test."""
    payload = {**VALID_BUS, "bus_number": f"TEST-{uuid.uuid4().hex[:6].upper()}"}
    resp = client.post("/api/v1/buses", json=payload)
    assert resp.status_code == 201, resp.text
    bus = resp.json()
    yield bus
    client.delete(f"/api/v1/buses/{bus['id']}")


# ── Tests ─────────────────────────────────────────────────────────────────────


@requires_db
class TestBusCRUD:

    def test_create_bus_returns_201(self, client: TestClient) -> None:
        payload = {"bus_number": f"TEST-{uuid.uuid4().hex[:6].upper()}", "route_id": "R1"}
        resp = client.post("/api/v1/buses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["bus_number"] == payload["bus_number"]
        assert data["status"] == "active"
        assert "id" in data
        # cleanup
        client.delete(f"/api/v1/buses/{data['id']}")

    def test_create_bus_default_status_active(self, client: TestClient) -> None:
        payload = {"bus_number": f"TEST-{uuid.uuid4().hex[:6].upper()}"}
        resp = client.post("/api/v1/buses", json=payload)
        assert resp.status_code == 201
        assert resp.json()["status"] == "active"
        client.delete(f"/api/v1/buses/{resp.json()['id']}")

    def test_create_duplicate_bus_returns_409(self, created_bus: dict, client: TestClient) -> None:
        resp = client.post("/api/v1/buses", json={"bus_number": created_bus["bus_number"]})
        assert resp.status_code == 409

    def test_get_bus_by_id(self, created_bus: dict, client: TestClient) -> None:
        resp = client.get(f"/api/v1/buses/{created_bus['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created_bus["id"]

    def test_get_bus_not_found(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/buses/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_get_bus_invalid_uuid(self, client: TestClient) -> None:
        resp = client.get("/api/v1/buses/not-a-uuid")
        assert resp.status_code == 422

    def test_list_buses(self, created_bus: dict, client: TestClient) -> None:
        resp = client.get("/api/v1/buses")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        ids = [b["id"] for b in resp.json()]
        assert created_bus["id"] in ids

    def test_update_bus(self, created_bus: dict, client: TestClient) -> None:
        resp = client.patch(
            f"/api/v1/buses/{created_bus['id']}",
            json={"status": "inactive", "route_id": "ROUTE-UPDATED"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "inactive"
        assert data["route_id"] == "ROUTE-UPDATED"

    def test_update_bus_not_found(self, client: TestClient) -> None:
        resp = client.patch(f"/api/v1/buses/{uuid.uuid4()}", json={"status": "inactive"})
        assert resp.status_code == 404

    def test_delete_bus(self, client: TestClient) -> None:
        payload = {"bus_number": f"DEL-{uuid.uuid4().hex[:6].upper()}"}
        create_resp = client.post("/api/v1/buses", json=payload)
        assert create_resp.status_code == 201
        bus_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/v1/buses/{bus_id}")
        assert del_resp.status_code == 204

        get_resp = client.get(f"/api/v1/buses/{bus_id}")
        assert get_resp.status_code == 404
