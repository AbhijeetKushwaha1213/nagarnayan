"""
Unit tests for DetectionService and EventService business logic.

Validates service-level rules (foreign key verification, bus-camera consistency,
lifecycle timestamp transitions) using isolated mock sessions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models.bus import Bus, BusStatus
from app.models.camera import Camera, CameraStatus, CameraType
from app.models.event import Event, EventSeverity, EventStatus, EventType
from app.models.stream import Stream, StreamProtocol, StreamStatus
from app.schemas.bus import BusCreate, BusUpdate
from app.schemas.camera import CameraCreate, CameraUpdate
from app.schemas.detection import DetectionCreate
from app.schemas.event import EventCreate, EventUpdate
from app.schemas.stream import StreamCreate, StreamUpdate
from app.services.bus import BusService
from app.services.camera import CameraService
from app.services.detection import DetectionService
from app.services.event import EventService
from app.services.stream import StreamService


@pytest.mark.asyncio
class TestDetectionServiceBusinessLogic:

    async def test_reject_nonexistent_bus(self) -> None:
        session = AsyncMock()
        service = DetectionService(session)
        service._bus_repo.get_by_id = AsyncMock(return_value=None)

        payload = DetectionCreate(
            bus_id=uuid.uuid4(),
            camera_id=uuid.uuid4(),
            detection_type="POTHOLE",
            confidence=0.9,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_detection(payload)
        assert exc_info.value.status_code == 422
        assert "Bus" in exc_info.value.detail
        assert "does not exist" in exc_info.value.detail

    async def test_reject_nonexistent_camera(self) -> None:
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
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_detection(payload)
        assert exc_info.value.status_code == 422
        assert "Camera" in exc_info.value.detail
        assert "does not exist" in exc_info.value.detail

    async def test_reject_camera_bus_mismatch(self) -> None:
        session = AsyncMock()
        service = DetectionService(session)
        bus_id1 = uuid.uuid4()
        bus_id2 = uuid.uuid4()
        cam_id = uuid.uuid4()

        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id1, bus_number="B1"))
        service._camera_repo.get_by_id = AsyncMock(
            return_value=Camera(id=cam_id, bus_id=bus_id2, camera_type=CameraType.front)
        )

        payload = DetectionCreate(
            bus_id=bus_id1,
            camera_id=cam_id,
            detection_type="POTHOLE",
            confidence=0.9,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_detection(payload)
        assert exc_info.value.status_code == 422
        assert "is mounted on bus" in exc_info.value.detail

    async def test_reject_nonexistent_event_link(self) -> None:
        session = AsyncMock()
        service = DetectionService(session)
        bus_id = uuid.uuid4()
        cam_id = uuid.uuid4()

        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="B1"))
        service._camera_repo.get_by_id = AsyncMock(
            return_value=Camera(id=cam_id, bus_id=bus_id, camera_type=CameraType.front)
        )
        service._event_repo.get_by_id = AsyncMock(return_value=None)

        payload = DetectionCreate(
            bus_id=bus_id,
            camera_id=cam_id,
            event_id=uuid.uuid4(),
            detection_type="POTHOLE",
            confidence=0.9,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_detection(payload)
        assert exc_info.value.status_code == 422
        assert "Event" in exc_info.value.detail
        assert "does not exist" in exc_info.value.detail

    async def test_reject_nonexistent_stream(self) -> None:
        session = AsyncMock()
        service = DetectionService(session)
        bus_id = uuid.uuid4()
        cam_id = uuid.uuid4()
        stream_id = uuid.uuid4()

        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="B1"))
        service._camera_repo.get_by_id = AsyncMock(
            return_value=Camera(id=cam_id, bus_id=bus_id, camera_type=CameraType.front)
        )
        service._stream_repo.get_by_id = AsyncMock(return_value=None)

        payload = DetectionCreate(
            bus_id=bus_id,
            camera_id=cam_id,
            stream_id=stream_id,
            detection_type="POTHOLE",
            confidence=0.9,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_detection(payload)
        assert exc_info.value.status_code == 422
        assert "Stream" in exc_info.value.detail
        assert "does not exist" in exc_info.value.detail

    async def test_reject_stream_camera_mismatch(self) -> None:
        session = AsyncMock()
        service = DetectionService(session)
        bus_id = uuid.uuid4()
        cam_id1 = uuid.uuid4()
        cam_id2 = uuid.uuid4()
        stream_id = uuid.uuid4()

        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="B1"))
        service._camera_repo.get_by_id = AsyncMock(
            return_value=Camera(id=cam_id1, bus_id=bus_id, camera_type=CameraType.front)
        )
        service._stream_repo.get_by_id = AsyncMock(
            return_value=Stream(id=stream_id, camera_id=cam_id2, stream_url="rtsp://localhost/test")
        )

        payload = DetectionCreate(
            bus_id=bus_id,
            camera_id=cam_id1,
            stream_id=stream_id,
            detection_type="POTHOLE",
            confidence=0.9,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_detection(payload)
        assert exc_info.value.status_code == 422
        assert "belongs to camera" in exc_info.value.detail

    async def test_create_valid_detection(self) -> None:
        session = AsyncMock()
        service = DetectionService(session)
        bus_id = uuid.uuid4()
        cam_id = uuid.uuid4()

        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="B1"))
        service._camera_repo.get_by_id = AsyncMock(
            return_value=Camera(id=cam_id, bus_id=bus_id, camera_type=CameraType.front)
        )
        service.repo.create = AsyncMock(side_effect=lambda d: d)
        service._correlation_service.correlate_and_link = AsyncMock(return_value=None)

        payload = DetectionCreate(
            bus_id=bus_id,
            camera_id=cam_id,
            detection_type="POTHOLE",
            confidence=0.92,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
            metadata={"model": "v1"},
        )

        det = await service.create_detection(payload)
        assert det.detection_type == "POTHOLE"
        assert det.confidence == 0.92
        assert det.latitude == 12.9716
        assert det.longitude == 77.5946
        assert det.extra_metadata == {"model": "v1"}
        assert det.location is not None


@pytest.mark.asyncio
class TestEventServiceBusinessLogic:

    async def test_create_event_lifecycle_defaults(self) -> None:
        session = AsyncMock()
        service = EventService(session)
        service.repo.create = AsyncMock(side_effect=lambda e: e)

        payload = EventCreate(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            status=EventStatus.DETECTED,
            latitude=12.9716,
            longitude=77.5946,
        )

        event = await service.create_event(payload)
        assert event.event_type == EventType.POTHOLE
        assert event.first_detected_at is not None
        assert event.last_detected_at is not None
        assert event.verified_at is None
        assert event.resolved_at is None
        assert event.location is not None

    async def test_create_event_verified_status(self) -> None:
        session = AsyncMock()
        service = EventService(session)
        service.repo.create = AsyncMock(side_effect=lambda e: e)

        payload = EventCreate(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            status=EventStatus.VERIFIED,
            latitude=12.9716,
            longitude=77.5946,
        )

        event = await service.create_event(payload)
        assert event.verified_at is not None
        assert event.resolved_at is None

    async def test_update_event_status_transitions(self) -> None:
        session = AsyncMock()
        service = EventService(session)
        event_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        existing = Event(
            id=event_id,
            event_type=EventType.POTHOLE,
            severity=EventSeverity.MEDIUM,
            status=EventStatus.DETECTED,
            latitude=12.9716,
            longitude=77.5946,
            confidence=0.9,
            first_detected_at=now,
            last_detected_at=now,
            verified_at=None,
            resolved_at=None,
            extra_metadata={},
        )
        service.get_event = AsyncMock(return_value=existing)
        service.repo.update = AsyncMock(side_effect=lambda obj, d: obj)

        # 1. Update to VERIFIED sets verified_at
        updated1 = await service.update_event(event_id, EventUpdate(status=EventStatus.VERIFIED))
        assert updated1.verified_at is not None
        assert updated1.resolved_at is None

        # 2. Update to RESOLVED sets resolved_at
        updated2 = await service.update_event(event_id, EventUpdate(status=EventStatus.RESOLVED))
        assert updated2.resolved_at is not None

    async def test_update_event_coordinates_updates_location(self) -> None:
        session = AsyncMock()
        service = EventService(session)
        event_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        existing = Event(
            id=event_id,
            event_type=EventType.POTHOLE,
            severity=EventSeverity.MEDIUM,
            status=EventStatus.OPEN,
            latitude=12.9716,
            longitude=77.5946,
            confidence=0.9,
            first_detected_at=now,
            last_detected_at=now,
            extra_metadata={},
        )
        service.get_event = AsyncMock(return_value=existing)
        service.repo.update = AsyncMock(side_effect=lambda obj, d: obj)

        updated = await service.update_event(
            event_id,
            EventUpdate(latitude=13.0000, longitude=78.0000),
        )
        assert updated.location is not None


@pytest.mark.asyncio
class TestBusServiceBusinessLogic:

    async def test_create_bus_success(self) -> None:
        session = AsyncMock()
        service = BusService(session)
        service.repo.get_by_bus_number = AsyncMock(return_value=None)
        service.repo.create = AsyncMock(side_effect=lambda b: b)

        payload = BusCreate(bus_number="KA-01-AB-1234", route_id="ROUTE-5", status=BusStatus.active)
        bus = await service.create_bus(payload)

        assert bus.bus_number == "KA-01-AB-1234"
        assert bus.route_id == "ROUTE-5"
        assert bus.status == BusStatus.active
        service.repo.create.assert_called_once()
        session.commit.assert_called_once()

    async def test_create_bus_duplicate_number_raises_409(self) -> None:
        session = AsyncMock()
        service = BusService(session)
        service.repo.get_by_bus_number = AsyncMock(return_value=Bus(bus_number="KA-01-AB-1234"))

        payload = BusCreate(bus_number="KA-01-AB-1234")
        with pytest.raises(HTTPException) as exc_info:
            await service.create_bus(payload)
        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail

    async def test_get_bus_not_found_raises_404(self) -> None:
        session = AsyncMock()
        service = BusService(session)
        service.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_bus(uuid.uuid4())
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

    async def test_update_bus_duplicate_number_raises_409(self) -> None:
        session = AsyncMock()
        service = BusService(session)
        bus_id = uuid.uuid4()
        other_id = uuid.uuid4()
        existing = Bus(id=bus_id, bus_number="KA-01-OLD")
        service.get_bus = AsyncMock(return_value=existing)
        service.repo.get_by_bus_number = AsyncMock(return_value=Bus(id=other_id, bus_number="KA-01-TAKEN"))

        with pytest.raises(HTTPException) as exc_info:
            await service.update_bus(bus_id, BusUpdate(bus_number="KA-01-TAKEN"))
        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail

    async def test_delete_bus_success(self) -> None:
        session = AsyncMock()
        service = BusService(session)
        bus = Bus(id=uuid.uuid4(), bus_number="KA-01-DEL")
        service.get_bus = AsyncMock(return_value=bus)
        service.repo.delete = AsyncMock()

        await service.delete_bus(bus.id)
        service.repo.delete.assert_called_once_with(bus)
        session.commit.assert_called_once()


@pytest.mark.asyncio
class TestCameraServiceBusinessLogic:

    async def test_create_camera_success(self) -> None:
        session = AsyncMock()
        service = CameraService(session)
        bus_id = uuid.uuid4()
        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="B1"))
        service.repo.create = AsyncMock(side_effect=lambda c: c)

        payload = CameraCreate(bus_id=bus_id, camera_type=CameraType.front, status=CameraStatus.active)
        cam = await service.create_camera(payload)

        assert cam.bus_id == bus_id
        assert cam.camera_type == CameraType.front
        assert cam.status == CameraStatus.active
        service.repo.create.assert_called_once()
        session.commit.assert_called_once()

    async def test_create_camera_nonexistent_bus_raises_422(self) -> None:
        session = AsyncMock()
        service = CameraService(session)
        service._bus_repo.get_by_id = AsyncMock(return_value=None)

        payload = CameraCreate(bus_id=uuid.uuid4(), camera_type=CameraType.rear)
        with pytest.raises(HTTPException) as exc_info:
            await service.create_camera(payload)
        assert exc_info.value.status_code == 422
        assert "does not exist" in exc_info.value.detail

    async def test_get_camera_not_found_raises_404(self) -> None:
        session = AsyncMock()
        service = CameraService(session)
        service.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_camera(uuid.uuid4())
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

    async def test_list_cameras_filter_by_bus_id(self) -> None:
        session = AsyncMock()
        service = CameraService(session)
        bus_id = uuid.uuid4()
        expected = [Camera(id=uuid.uuid4(), bus_id=bus_id, camera_type=CameraType.front)]
        service.repo.get_by_bus_id = AsyncMock(return_value=expected)

        result = await service.list_cameras(bus_id=bus_id)
        assert result == expected
        service.repo.get_by_bus_id.assert_called_once_with(bus_id)

    async def test_delete_camera_success(self) -> None:
        session = AsyncMock()
        service = CameraService(session)
        cam = Camera(id=uuid.uuid4(), bus_id=uuid.uuid4(), camera_type=CameraType.side)
        service.get_camera = AsyncMock(return_value=cam)
        service.repo.delete = AsyncMock()

        await service.delete_camera(cam.id)
        service.repo.delete.assert_called_once_with(cam)
        session.commit.assert_called_once()


@pytest.mark.asyncio
class TestStreamServiceBusinessLogic:

    async def test_create_stream_success(self) -> None:
        session = AsyncMock()
        service = StreamService(session)
        cam_id = uuid.uuid4()
        service._camera_repo.get_by_id = AsyncMock(
            return_value=Camera(id=cam_id, bus_id=uuid.uuid4(), camera_type=CameraType.front)
        )
        service.repo.create = AsyncMock(side_effect=lambda s: s)

        payload = StreamCreate(
            camera_id=cam_id,
            stream_url="rtsp://localhost:8554/bus/front",
            protocol=StreamProtocol.rtsp,
            status=StreamStatus.inactive,
        )
        stream = await service.create_stream(payload)

        assert stream.camera_id == cam_id
        assert stream.stream_url == "rtsp://localhost:8554/bus/front"
        assert stream.protocol == StreamProtocol.rtsp
        service.repo.create.assert_called_once()
        session.commit.assert_called_once()

    async def test_create_stream_nonexistent_camera_raises_422(self) -> None:
        session = AsyncMock()
        service = StreamService(session)
        service._camera_repo.get_by_id = AsyncMock(return_value=None)

        payload = StreamCreate(
            camera_id=uuid.uuid4(),
            stream_url="rtsp://localhost:8554/bus/front",
        )
        with pytest.raises(HTTPException) as exc_info:
            await service.create_stream(payload)
        assert exc_info.value.status_code == 422
        assert "does not exist" in exc_info.value.detail

    async def test_get_stream_not_found_raises_404(self) -> None:
        session = AsyncMock()
        service = StreamService(session)
        service.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_stream(uuid.uuid4())
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

    async def test_list_streams_filter_by_camera_id(self) -> None:
        session = AsyncMock()
        service = StreamService(session)
        cam_id = uuid.uuid4()
        expected = [
            Stream(
                id=uuid.uuid4(),
                camera_id=cam_id,
                stream_url="rtsp://localhost:8554/test",
                protocol=StreamProtocol.rtsp,
            )
        ]
        service.repo.get_by_camera_id = AsyncMock(return_value=expected)

        result = await service.list_streams(camera_id=cam_id)
        assert result == expected
        service.repo.get_by_camera_id.assert_called_once_with(cam_id)

    async def test_delete_stream_success(self) -> None:
        session = AsyncMock()
        service = StreamService(session)
        stream = Stream(id=uuid.uuid4(), camera_id=uuid.uuid4(), stream_url="rtsp://localhost:8554/del")
        service.get_stream = AsyncMock(return_value=stream)
        service.repo.delete = AsyncMock()

        await service.delete_stream(stream.id)
        service.repo.delete.assert_called_once_with(stream)
        session.commit.assert_called_once()


@pytest.mark.asyncio
class TestPhase2PhysicalHierarchyLifecycle:
    """
    Validates the end-to-end Phase 2 Physical Infrastructure Hierarchy:
    Bus -> Camera -> Stream
    """

    async def test_bus_camera_stream_hierarchy_lifecycle(self) -> None:
        session = AsyncMock()
        bus_service = BusService(session)
        camera_service = CameraService(session)
        stream_service = StreamService(session)

        # 1. Create Bus
        bus_id = uuid.uuid4()
        bus_payload = BusCreate(bus_number="DL-01-AB-9999", route_id="ROUTE-AIRPORT-1", status=BusStatus.active)
        bus_service.repo.get_by_bus_number = AsyncMock(return_value=None)
        bus_service.repo.create = AsyncMock(side_effect=lambda b: setattr(b, "id", bus_id) or b)

        created_bus = await bus_service.create_bus(bus_payload)
        assert created_bus.id == bus_id
        assert created_bus.bus_number == "DL-01-AB-9999"
        assert created_bus.route_id == "ROUTE-AIRPORT-1"
        assert created_bus.status == BusStatus.active

        # 2. Create Camera mounted on that Bus
        cam_id = uuid.uuid4()
        camera_service._bus_repo.get_by_id = AsyncMock(return_value=created_bus)
        camera_service.repo.create = AsyncMock(side_effect=lambda c: setattr(c, "id", cam_id) or c)

        cam_payload = CameraCreate(bus_id=created_bus.id, camera_type=CameraType.front, status=CameraStatus.active)
        created_camera = await camera_service.create_camera(cam_payload)
        assert created_camera.id == cam_id
        assert created_camera.bus_id == created_bus.id
        assert created_camera.camera_type == CameraType.front

        # 3. Create Stream associated with that Camera
        stream_id = uuid.uuid4()
        stream_service._camera_repo.get_by_id = AsyncMock(return_value=created_camera)
        stream_service.repo.create = AsyncMock(side_effect=lambda s: setattr(s, "id", stream_id) or s)

        stream_payload = StreamCreate(
            camera_id=created_camera.id,
            stream_url="rtsp://localhost:8554/bus/front",
            protocol=StreamProtocol.rtsp,
            status=StreamStatus.inactive,
        )
        created_stream = await stream_service.create_stream(stream_payload)
        assert created_stream.id == stream_id
        assert created_stream.camera_id == created_camera.id
        assert created_stream.stream_url == "rtsp://localhost:8554/bus/front"
        assert created_stream.protocol == StreamProtocol.rtsp

        # 4. Verify Relationships
        # Bus has cameras, Camera has streams
        created_bus.cameras = [created_camera]
        created_camera.bus = created_bus
        created_camera.streams = [created_stream]
        created_stream.camera = created_camera

        assert len(created_bus.cameras) == 1
        assert created_bus.cameras[0].id == created_camera.id
        assert created_camera.bus.id == created_bus.id
        assert len(created_camera.streams) == 1
        assert created_camera.streams[0].id == created_stream.id
        assert created_stream.camera.id == created_camera.id


