"""
Tests for Stream CRUD API — /api/v1/streams

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
    resp = client.post(
        "/api/v1/buses",
        json={"bus_number": f"STR-BUS-{uuid.uuid4().hex[:6].upper()}"},
    )
    assert resp.status_code == 201
    bus = resp.json()
    yield bus
    client.delete(f"/api/v1/buses/{bus['id']}")


@pytest.fixture(scope="module")
def test_camera(client: TestClient, test_bus: dict) -> dict:
    resp = client.post(
        "/api/v1/cameras",
        json={"bus_id": test_bus["id"], "camera_type": "front"},
    )
    assert resp.status_code == 201
    camera = resp.json()
    yield camera
    client.delete(f"/api/v1/cameras/{camera['id']}")


@pytest.fixture
def created_stream(client: TestClient, test_camera: dict) -> dict:
    resp = client.post(
        "/api/v1/streams",
        json={
            "camera_id": test_camera["id"],
            "stream_url": f"rtsp://localhost:8554/bus/test/{uuid.uuid4().hex[:6]}",
        },
    )
    assert resp.status_code == 201
    stream = resp.json()
    yield stream
    client.delete(f"/api/v1/streams/{stream['id']}")


# ── Tests ─────────────────────────────────────────────────────────────────────


@requires_db
class TestStreamCRUD:

    def test_create_stream_returns_201(self, client: TestClient, test_camera: dict) -> None:
        resp = client.post(
            "/api/v1/streams",
            json={
                "camera_id": test_camera["id"],
                "stream_url": f"rtsp://localhost:8554/test/{uuid.uuid4().hex[:6]}",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["camera_id"] == test_camera["id"]
        assert data["protocol"] == "rtsp"
        assert data["status"] == "inactive"
        client.delete(f"/api/v1/streams/{data['id']}")

    def test_create_stream_invalid_camera_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/streams",
            json={
                "camera_id": str(uuid.uuid4()),
                "stream_url": "rtsp://localhost:8554/test",
            },
        )
        assert resp.status_code == 422

    def test_create_stream_invalid_url_returns_422(
        self, client: TestClient, test_camera: dict
    ) -> None:
        resp = client.post(
            "/api/v1/streams",
            json={
                "camera_id": test_camera["id"],
                "stream_url": "http://not-an-rtsp-url.com",
            },
        )
        assert resp.status_code == 422

    def test_get_stream_by_id(self, client: TestClient, created_stream: dict) -> None:
        resp = client.get(f"/api/v1/streams/{created_stream['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created_stream["id"]

    def test_get_stream_not_found(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/streams/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_list_streams(self, client: TestClient, created_stream: dict) -> None:
        resp = client.get("/api/v1/streams")
        assert resp.status_code == 200
        ids = [s["id"] for s in resp.json()]
        assert created_stream["id"] in ids

    def test_list_streams_filter_by_camera(
        self, client: TestClient, test_camera: dict, created_stream: dict
    ) -> None:
        resp = client.get(f"/api/v1/streams?camera_id={test_camera['id']}")
        assert resp.status_code == 200
        for stream in resp.json():
            assert stream["camera_id"] == test_camera["id"]

    def test_update_stream(self, client: TestClient, created_stream: dict) -> None:
        resp = client.patch(
            f"/api/v1/streams/{created_stream['id']}",
            json={"status": "active"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_stream_url_stored_as_metadata(
        self, client: TestClient, created_stream: dict
    ) -> None:
        """Verify stream_url is stored and returned — not consumed by the backend."""
        resp = client.get(f"/api/v1/streams/{created_stream['id']}")
        assert resp.json()["stream_url"] == created_stream["stream_url"]

    def test_delete_stream(self, client: TestClient, test_camera: dict) -> None:
        create_resp = client.post(
            "/api/v1/streams",
            json={
                "camera_id": test_camera["id"],
                "stream_url": f"rtsp://localhost:8554/del/{uuid.uuid4().hex[:6]}",
            },
        )
        assert create_resp.status_code == 201
        stream_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/v1/streams/{stream_id}")
        assert del_resp.status_code == 204

        get_resp = client.get(f"/api/v1/streams/{stream_id}")
        assert get_resp.status_code == 404
