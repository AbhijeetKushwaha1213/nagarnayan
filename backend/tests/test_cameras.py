"""
Tests for Camera CRUD API — /api/v1/cameras

Requires DATABASE_URL and asyncpg. Skipped otherwise.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from tests.conftest import requires_db


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def test_bus(client: TestClient) -> dict:
    """Create a bus used across camera tests."""
    resp = client.post(
        "/api/v1/buses",
        json={"bus_number": f"CAM-BUS-{uuid.uuid4().hex[:6].upper()}"},
    )
    assert resp.status_code == 201
    bus = resp.json()
    yield bus
    client.delete(f"/api/v1/buses/{bus['id']}")


@pytest.fixture
def created_camera(client: TestClient, test_bus: dict) -> dict:
    """Create a camera and delete it after the test."""
    resp = client.post(
        "/api/v1/cameras",
        json={"bus_id": test_bus["id"], "camera_type": "front"},
    )
    assert resp.status_code == 201
    camera = resp.json()
    yield camera
    client.delete(f"/api/v1/cameras/{camera['id']}")


# ── Tests ─────────────────────────────────────────────────────────────────────


@requires_db
class TestCameraCRUD:

    def test_create_camera_returns_201(self, client: TestClient, test_bus: dict) -> None:
        resp = client.post(
            "/api/v1/cameras",
            json={"bus_id": test_bus["id"], "camera_type": "rear"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["bus_id"] == test_bus["id"]
        assert data["camera_type"] == "rear"
        assert data["status"] == "active"
        client.delete(f"/api/v1/cameras/{data['id']}")

    def test_create_camera_invalid_bus_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/cameras",
            json={"bus_id": str(uuid.uuid4()), "camera_type": "front"},
        )
        assert resp.status_code == 422

    def test_create_camera_invalid_type_returns_422(
        self, client: TestClient, test_bus: dict
    ) -> None:
        resp = client.post(
            "/api/v1/cameras",
            json={"bus_id": test_bus["id"], "camera_type": "INVALID_TYPE"},
        )
        assert resp.status_code == 422

    def test_get_camera_by_id(self, client: TestClient, created_camera: dict) -> None:
        resp = client.get(f"/api/v1/cameras/{created_camera['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created_camera["id"]

    def test_get_camera_not_found(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/cameras/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_list_cameras(self, client: TestClient, created_camera: dict) -> None:
        resp = client.get("/api/v1/cameras")
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json()]
        assert created_camera["id"] in ids

    def test_list_cameras_filter_by_bus(
        self, client: TestClient, test_bus: dict, created_camera: dict
    ) -> None:
        resp = client.get(f"/api/v1/cameras?bus_id={test_bus['id']}")
        assert resp.status_code == 200
        for cam in resp.json():
            assert cam["bus_id"] == test_bus["id"]

    def test_update_camera(self, client: TestClient, created_camera: dict) -> None:
        resp = client.patch(
            f"/api/v1/cameras/{created_camera['id']}",
            json={"status": "error"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_delete_camera(self, client: TestClient, test_bus: dict) -> None:
        create_resp = client.post(
            "/api/v1/cameras",
            json={"bus_id": test_bus["id"], "camera_type": "interior"},
        )
        assert create_resp.status_code == 201
        cam_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/v1/cameras/{cam_id}")
        assert del_resp.status_code == 204

        get_resp = client.get(f"/api/v1/cameras/{cam_id}")
        assert get_resp.status_code == 404
