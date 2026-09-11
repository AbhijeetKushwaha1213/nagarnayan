"""
Tests for Detection API — /api/v1/detections

Validates AI observation ingestion, Pydantic validation (confidence, coordinates),
foreign key checks, and filtering.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from tests.conftest import requires_db
from app.core.database import get_db
from app.main import app


class TestDetectionValidation:
    """Tests that exercise Pydantic schema validation without needing a database."""

    @pytest.fixture(autouse=True)
    def override_get_db(self) -> None:
        async def dummy_db():
            yield None

        app.dependency_overrides[get_db] = dummy_db
        yield
        app.dependency_overrides.pop(get_db, None)

    def test_reject_invalid_confidence_too_high(self, client: TestClient) -> None:
        payload = {
            "bus_id": str(uuid.uuid4()),
            "camera_id": str(uuid.uuid4()),
            "detection_type": "POTHOLE",
            "confidence": 1.5,  # must be <= 1.0
            "latitude": 12.9716,
            "longitude": 77.5946,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = client.post("/api/v1/detections", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_confidence_negative(self, client: TestClient) -> None:
        payload = {
            "bus_id": str(uuid.uuid4()),
            "camera_id": str(uuid.uuid4()),
            "detection_type": "POTHOLE",
            "confidence": -0.1,  # must be >= 0.0
            "latitude": 12.9716,
            "longitude": 77.5946,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = client.post("/api/v1/detections", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_latitude_too_high(self, client: TestClient) -> None:
        payload = {
            "bus_id": str(uuid.uuid4()),
            "camera_id": str(uuid.uuid4()),
            "detection_type": "POTHOLE",
            "confidence": 0.9,
            "latitude": 95.0,  # must be <= 90.0
            "longitude": 77.5946,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = client.post("/api/v1/detections", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_latitude_too_low(self, client: TestClient) -> None:
        payload = {
            "bus_id": str(uuid.uuid4()),
            "camera_id": str(uuid.uuid4()),
            "detection_type": "POTHOLE",
            "confidence": 0.9,
            "latitude": -95.0,  # must be >= -90.0
            "longitude": 77.5946,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = client.post("/api/v1/detections", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_longitude_too_high(self, client: TestClient) -> None:
        payload = {
            "bus_id": str(uuid.uuid4()),
            "camera_id": str(uuid.uuid4()),
            "detection_type": "POTHOLE",
            "confidence": 0.9,
            "latitude": 12.9716,
            "longitude": 185.0,  # must be <= 180.0
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = client.post("/api/v1/detections", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_longitude_too_low(self, client: TestClient) -> None:
        payload = {
            "bus_id": str(uuid.uuid4()),
            "camera_id": str(uuid.uuid4()),
            "detection_type": "POTHOLE",
            "confidence": 0.9,
            "latitude": 12.9716,
            "longitude": -185.0,  # must be >= -180.0
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = client.post("/api/v1/detections", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_uuid_format(self, client: TestClient) -> None:
        resp = client.get("/api/v1/detections/invalid-uuid-string")
        assert resp.status_code == 422

    def test_reject_missing_required_fields(self, client: TestClient) -> None:
        resp = client.post("/api/v1/detections", json={})
        assert resp.status_code == 422

    def test_accept_payload_without_coordinates(self) -> None:
        """Video AI detections without GPS telemetry should validate successfully."""
        from app.schemas.detection import DetectionCreate

        data = DetectionCreate(
            bus_id=uuid.uuid4(),
            camera_id=uuid.uuid4(),
            detection_type="POTHOLE",
            confidence=0.85,
            detected_at=datetime.now(timezone.utc),
            latitude=None,
            longitude=None,
        )
        assert data.latitude is None
        assert data.longitude is None
        assert data.detection_type == "POTHOLE"


@requires_db
class TestDetectionCRUD:
    """Full database lifecycle tests for detections."""

    @pytest.fixture
    def setup_bus_and_camera(self, client: TestClient) -> dict:
        # Create a bus
        bus_resp = client.post(
            "/api/v1/buses",
            json={"bus_number": f"DET-BUS-{uuid.uuid4().hex[:6].upper()}"},
        )
        assert bus_resp.status_code == 201
        bus = bus_resp.json()

        # Create a camera
        cam_resp = client.post(
            "/api/v1/cameras",
            json={"bus_id": bus["id"], "camera_type": "front"},
        )
        assert cam_resp.status_code == 201
        camera = cam_resp.json()

        yield {"bus": bus, "camera": camera}

        # Cleanup
        client.delete(f"/api/v1/buses/{bus['id']}")

    def test_reject_nonexistent_bus(self, client: TestClient) -> None:
        payload = {
            "bus_id": str(uuid.uuid4()),
            "camera_id": str(uuid.uuid4()),
            "detection_type": "POTHOLE",
            "confidence": 0.95,
            "latitude": 12.9716,
            "longitude": 77.5946,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = client.post("/api/v1/detections", json=payload)
        assert resp.status_code == 422
        assert "does not exist" in resp.json()["detail"]

    def test_reject_nonexistent_camera(self, setup_bus_and_camera: dict, client: TestClient) -> None:
        bus = setup_bus_and_camera["bus"]
        payload = {
            "bus_id": bus["id"],
            "camera_id": str(uuid.uuid4()),
            "detection_type": "POTHOLE",
            "confidence": 0.95,
            "latitude": 12.9716,
            "longitude": 77.5946,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = client.post("/api/v1/detections", json=payload)
        assert resp.status_code == 422
        assert "Camera" in resp.json()["detail"]

    def test_create_valid_detection(self, setup_bus_and_camera: dict, client: TestClient) -> None:
        bus = setup_bus_and_camera["bus"]
        camera = setup_bus_and_camera["camera"]
        now = datetime.now(timezone.utc).isoformat()

        payload = {
            "bus_id": bus["id"],
            "camera_id": camera["id"],
            "detection_type": "POTHOLE",
            "confidence": 0.92,
            "latitude": 12.9716,
            "longitude": 77.5946,
            "detected_at": now,
            "frame_reference": "frame_00123.jpg",
            "metadata": {"model_version": "v1.0", "bbox": [10, 20, 100, 200]},
        }
        resp = client.post("/api/v1/detections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["detection_type"] == "POTHOLE"
        assert data["confidence"] == 0.92
        assert data["latitude"] == 12.9716
        assert data["longitude"] == 77.5946
        assert data["metadata"]["model_version"] == "v1.0"
        assert "id" in data

    def test_retrieve_detection(self, setup_bus_and_camera: dict, client: TestClient) -> None:
        bus = setup_bus_and_camera["bus"]
        camera = setup_bus_and_camera["camera"]

        create_resp = client.post(
            "/api/v1/detections",
            json={
                "bus_id": bus["id"],
                "camera_id": camera["id"],
                "detection_type": "WATERLOGGING",
                "confidence": 0.88,
                "latitude": 12.9720,
                "longitude": 77.5950,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert create_resp.status_code == 201
        det_id = create_resp.json()["id"]

        get_resp = client.get(f"/api/v1/detections/{det_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == det_id
        assert get_resp.json()["detection_type"] == "WATERLOGGING"

    def test_retrieve_detection_not_found(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/detections/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_list_detections(self, setup_bus_and_camera: dict, client: TestClient) -> None:
        resp = client.get("/api/v1/detections")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_filter_by_bus(self, setup_bus_and_camera: dict, client: TestClient) -> None:
        bus = setup_bus_and_camera["bus"]
        resp = client.get(f"/api/v1/detections?bus_id={bus['id']}")
        assert resp.status_code == 200
        for d in resp.json():
            assert d["bus_id"] == bus["id"]

    def test_filter_by_camera(self, setup_bus_and_camera: dict, client: TestClient) -> None:
        camera = setup_bus_and_camera["camera"]
        resp = client.get(f"/api/v1/detections?camera_id={camera['id']}")
        assert resp.status_code == 200
        for d in resp.json():
            assert d["camera_id"] == camera["id"]

    def test_filter_by_type(self, setup_bus_and_camera: dict, client: TestClient) -> None:
        resp = client.get("/api/v1/detections?detection_type=POTHOLE")
        assert resp.status_code == 200
        for d in resp.json():
            assert d["detection_type"] == "POTHOLE"
