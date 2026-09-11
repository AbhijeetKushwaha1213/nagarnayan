"""
Tests for Phase 4A: AI Detection Ingestion Contract.

Validates the contract between the external AI Video Intelligence Service
and the Nagar Nayan Backend:
  1. Valid AI detection submission
  2. Invalid bus reference (422)
  3. Invalid camera reference (422)
  4. Camera / Bus mismatch (422)
  5. Invalid stream reference (422)
  6. Stream / Camera mismatch (422)
  7. Invalid confidence score (422)
  8. Invalid coordinates (422)
  9. Duplicate / retry behavior (idempotency)
 10. Model-specific metadata persistence (bounding box, tracking_id, model_version)
 11. Response format contract (detection_id, camera_id, bus_id, stream_id, etc.)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.bus import Bus
from app.models.camera import Camera, CameraType
from app.models.detection import Detection
from app.models.stream import Stream
from app.schemas.detection import DetectionCreate, DetectionResponse
from app.services.detection import DetectionService


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


class TestAIIngestionSchemaAndValidation:
    """Tests 7, 8: Schema-level validation for AI detection submissions."""

    @pytest.fixture(autouse=True)
    def override_get_db(self) -> None:
        async def dummy_db():
            yield None

        app.dependency_overrides[get_db] = dummy_db
        yield
        app.dependency_overrides.pop(get_db, None)

    def test_7_invalid_confidence_above_1(self, test_client: TestClient) -> None:
        payload = {
            "bus_id": str(uuid.uuid4()),
            "camera_id": str(uuid.uuid4()),
            "detection_type": "POTHOLE",
            "confidence": 1.05,
            "latitude": 12.9716,
            "longitude": 77.5946,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = test_client.post("/api/v1/detections", json=payload)
        assert resp.status_code == 422

    def test_7_invalid_confidence_negative(self, test_client: TestClient) -> None:
        payload = {
            "bus_id": str(uuid.uuid4()),
            "camera_id": str(uuid.uuid4()),
            "detection_type": "POTHOLE",
            "confidence": -0.05,
            "latitude": 12.9716,
            "longitude": 77.5946,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = test_client.post("/api/v1/detections", json=payload)
        assert resp.status_code == 422

    def test_8_invalid_coordinates_latitude_out_of_bounds(self, test_client: TestClient) -> None:
        payload = {
            "bus_id": str(uuid.uuid4()),
            "camera_id": str(uuid.uuid4()),
            "detection_type": "POTHOLE",
            "confidence": 0.95,
            "latitude": 91.5,
            "longitude": 77.5946,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = test_client.post("/api/v1/detections", json=payload)
        assert resp.status_code == 422

    def test_8_invalid_coordinates_longitude_out_of_bounds(self, test_client: TestClient) -> None:
        payload = {
            "bus_id": str(uuid.uuid4()),
            "camera_id": str(uuid.uuid4()),
            "detection_type": "POTHOLE",
            "confidence": 0.95,
            "latitude": 12.9716,
            "longitude": -185.0,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = test_client.post("/api/v1/detections", json=payload)
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestAISourceIdentificationAndContract:
    """Tests 1–6, 9–11: Service-level source verification, retry idempotency, and metadata."""

    async def test_1_valid_ai_detection_submission(self) -> None:
        session = AsyncMock()
        service = DetectionService(session)

        bus_id = uuid.uuid4()
        cam_id = uuid.uuid4()
        stream_id = uuid.uuid4()
        det_id = uuid.uuid4()

        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="DL-01-100"))
        service._camera_repo.get_by_id = AsyncMock(return_value=Camera(id=cam_id, bus_id=bus_id, camera_type=CameraType.front))
        service._stream_repo.get_by_id = AsyncMock(return_value=Stream(id=stream_id, camera_id=cam_id, stream_url="rtsp://localhost/bus"))
        service.repo.find_duplicate = AsyncMock(return_value=None)
        service.repo.create = AsyncMock(side_effect=lambda d: setattr(d, "id", det_id) or d)
        service._correlation_service.correlate_and_link = AsyncMock(return_value=None)

        payload = DetectionCreate(
            bus_id=bus_id,
            camera_id=cam_id,
            stream_id=stream_id,
            detection_type="POTHOLE",
            confidence=0.94,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
            frame_reference="frame_000456",
            metadata={"model": "yolo", "class_id": 3},
        )

        det = await service.create_detection(payload)
        assert det.id == det_id
        assert det.bus_id == bus_id
        assert det.camera_id == cam_id
        assert det.stream_id == stream_id
        assert det.detection_type == "POTHOLE"
        assert det.confidence == 0.94
        assert det.extra_metadata["model"] == "yolo"

    async def test_2_invalid_bus_returns_422(self) -> None:
        session = AsyncMock()
        service = DetectionService(session)
        service._bus_repo.get_by_id = AsyncMock(return_value=None)

        payload = DetectionCreate(
            bus_id=uuid.uuid4(),
            camera_id=uuid.uuid4(),
            detection_type="POTHOLE",
            confidence=0.9,
            detected_at=datetime.now(timezone.utc),
        )
        with pytest.raises(Exception) as exc:
            await service.create_detection(payload)
        assert exc.value.status_code == 422
        assert "Bus" in exc.value.detail

    async def test_3_invalid_camera_returns_422(self) -> None:
        session = AsyncMock()
        service = DetectionService(session)
        bus_id = uuid.uuid4()
        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="B1"))
        service._camera_repo.get_by_id = AsyncMock(return_value=None)

        payload = DetectionCreate(
            bus_id=bus_id,
            camera_id=uuid.uuid4(),
            detection_type="POTHOLE",
            confidence=0.9,
            detected_at=datetime.now(timezone.utc),
        )
        with pytest.raises(Exception) as exc:
            await service.create_detection(payload)
        assert exc.value.status_code == 422
        assert "Camera" in exc.value.detail

    async def test_4_camera_bus_mismatch_returns_422(self) -> None:
        session = AsyncMock()
        service = DetectionService(session)
        bus_id_1 = uuid.uuid4()
        bus_id_2 = uuid.uuid4()
        cam_id = uuid.uuid4()

        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id_1, bus_number="B1"))
        service._camera_repo.get_by_id = AsyncMock(return_value=Camera(id=cam_id, bus_id=bus_id_2, camera_type=CameraType.front))

        payload = DetectionCreate(
            bus_id=bus_id_1,
            camera_id=cam_id,
            detection_type="POTHOLE",
            confidence=0.9,
            detected_at=datetime.now(timezone.utc),
        )
        with pytest.raises(Exception) as exc:
            await service.create_detection(payload)
        assert exc.value.status_code == 422
        assert "is mounted on bus" in exc.value.detail

    async def test_5_invalid_stream_returns_422(self) -> None:
        session = AsyncMock()
        service = DetectionService(session)
        bus_id = uuid.uuid4()
        cam_id = uuid.uuid4()
        stream_id = uuid.uuid4()

        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="B1"))
        service._camera_repo.get_by_id = AsyncMock(return_value=Camera(id=cam_id, bus_id=bus_id, camera_type=CameraType.front))
        service._stream_repo.get_by_id = AsyncMock(return_value=None)

        payload = DetectionCreate(
            bus_id=bus_id,
            camera_id=cam_id,
            stream_id=stream_id,
            detection_type="POTHOLE",
            confidence=0.9,
            detected_at=datetime.now(timezone.utc),
        )
        with pytest.raises(Exception) as exc:
            await service.create_detection(payload)
        assert exc.value.status_code == 422
        assert "Stream" in exc.value.detail

    async def test_6_stream_camera_mismatch_returns_422(self) -> None:
        session = AsyncMock()
        service = DetectionService(session)
        bus_id = uuid.uuid4()
        cam_id_1 = uuid.uuid4()
        cam_id_2 = uuid.uuid4()
        stream_id = uuid.uuid4()

        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="B1"))
        service._camera_repo.get_by_id = AsyncMock(return_value=Camera(id=cam_id_1, bus_id=bus_id, camera_type=CameraType.front))
        service._stream_repo.get_by_id = AsyncMock(return_value=Stream(id=stream_id, camera_id=cam_id_2, stream_url="rtsp://localhost/test"))

        payload = DetectionCreate(
            bus_id=bus_id,
            camera_id=cam_id_1,
            stream_id=stream_id,
            detection_type="POTHOLE",
            confidence=0.9,
            detected_at=datetime.now(timezone.utc),
        )
        with pytest.raises(Exception) as exc:
            await service.create_detection(payload)
        assert exc.value.status_code == 422
        assert "belongs to camera" in exc.value.detail

    async def test_9_duplicate_retry_idempotency(self) -> None:
        """When an AI client retries a request with the same frame_reference, return existing detection."""
        session = AsyncMock()
        service = DetectionService(session)
        bus_id = uuid.uuid4()
        cam_id = uuid.uuid4()
        det_id = uuid.uuid4()

        existing_det = Detection(
            id=det_id,
            camera_id=cam_id,
            bus_id=bus_id,
            detection_type="POTHOLE",
            confidence=0.92,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
            frame_reference="frame_000123",
            extra_metadata={"model": "yolo"},
        )

        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="B1"))
        service._camera_repo.get_by_id = AsyncMock(return_value=Camera(id=cam_id, bus_id=bus_id, camera_type=CameraType.front))
        service.repo.find_duplicate = AsyncMock(return_value=existing_det)
        service.repo.create = AsyncMock()

        payload = DetectionCreate(
            bus_id=bus_id,
            camera_id=cam_id,
            detection_type="POTHOLE",
            confidence=0.92,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
            frame_reference="frame_000123",
        )

        # Ingestion call (retry)
        result = await service.create_detection(payload)

        # Must return the existing record without creating a new duplicate
        assert result.id == det_id
        service.repo.create.assert_not_called()

    async def test_10_metadata_persistence(self) -> None:
        """Verify complex model-specific metadata (bounding box, tracking_id) persists cleanly."""
        session = AsyncMock()
        service = DetectionService(session)
        bus_id = uuid.uuid4()
        cam_id = uuid.uuid4()

        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="B1"))
        service._camera_repo.get_by_id = AsyncMock(return_value=Camera(id=cam_id, bus_id=bus_id, camera_type=CameraType.front))
        service.repo.find_duplicate = AsyncMock(return_value=None)
        service.repo.create = AsyncMock(side_effect=lambda d: d)
        service._correlation_service.correlate_and_link = AsyncMock(return_value=None)

        ai_metadata = {
            "model": "yolo",
            "model_version": "v1",
            "class_id": 2,
            "tracking_id": 45,
            "bounding_box": {"x1": 100, "y1": 100, "x2": 300, "y2": 250},
        }

        payload = DetectionCreate(
            bus_id=bus_id,
            camera_id=cam_id,
            detection_type="POTHOLE",
            confidence=0.88,
            detected_at=datetime.now(timezone.utc),
            metadata=ai_metadata,
        )

        det = await service.create_detection(payload)
        assert det.extra_metadata == ai_metadata
        assert det.extra_metadata["bounding_box"]["x1"] == 100
        assert det.extra_metadata["tracking_id"] == 45

    async def test_11_response_format_contract(self) -> None:
        """Verify DetectionResponse serializes all required contract fields including detection_id."""
        det_id = uuid.uuid4()
        cam_id = uuid.uuid4()
        bus_id = uuid.uuid4()
        stream_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        fake_detection = Detection(
            id=det_id,
            camera_id=cam_id,
            bus_id=bus_id,
            stream_id=stream_id,
            detection_type="POTHOLE",
            confidence=0.91,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=now,
            frame_reference="frame_001",
            extra_metadata={"model": "yolo"},
            event_id=None,
            created_at=now,
        )

        response_obj = DetectionResponse.model_validate(fake_detection)
        data = response_obj.model_dump(mode="json")

        assert data["id"] == str(det_id)
        assert data["detection_id"] == str(det_id)
        assert data["camera_id"] == str(cam_id)
        assert data["bus_id"] == str(bus_id)
        assert data["stream_id"] == str(stream_id)
        assert data["detection_type"] == "POTHOLE"
        assert data["confidence"] == 0.91
        assert data["latitude"] == 12.9716
        assert data["longitude"] == 77.5946
        assert "detected_at" in data
        assert "created_at" in data
