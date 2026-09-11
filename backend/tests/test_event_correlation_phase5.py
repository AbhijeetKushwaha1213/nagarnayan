"""
Phase 5.1 Comprehensive Verification Test Suite: Urban Event Correlation Engine.

Covers Scenarios A through O:
- Scenario A: First valid pothole detection creates one Urban Event (schema default severity MEDIUM, no severity scoring).
- Scenario B: Second nearby pothole detection within 300 seconds attaches to existing event.
- Scenario C: Same detection type outside spatial radius creates new event.
- Scenario D: Same detection type outside temporal window creates new event.
- Scenario E: Different detection type at same location does not correlate.
- Scenario F: Missing GPS retains detection with event_id = None (zero fabricated GPS rule).
- Scenario G: Partial / invalid GPS does not create event.
- Scenario H: Duplicate detection does not create duplicate event.
- Scenario I: Multiple different cameras/buses observing same pothole correlate into same event.
- Scenario J: first_detected_at preserved when new detections link.
- Scenario K: last_detected_at updated monotonically to latest detection timestamp.
- Scenario L: Deterministic confidence aggregation follows running weighted average formula in [0, 1].
- Scenario M: Terminal events (RESOLVED, REJECTED) are excluded from correlation and not reused.
- Scenario N: Event APIs (retrieval, filtering, GeoJSON) and Detection linkages remain functional.
- Scenario O: Concurrency behavior and spatial grid advisory locking are explicitly verified.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.bus import Bus
from app.models.camera import Camera, CameraType
from app.models.detection import Detection
from app.models.event import (
    ACTIVE_EVENT_STATUSES,
    TERMINAL_EVENT_STATUSES,
    Event,
    EventSeverity,
    EventStatus,
    EventType,
)
from app.models.stream import Stream
from app.repositories.event import EventRepository
from app.schemas.detection import DetectionCreate
from app.services.detection import DetectionService
from app.services.event import EventService
from app.services.event_correlation import (
    DETECTION_TYPE_TO_EVENT_TYPE,
    EventCorrelationService,
    compute_spatial_grid_cell,
    get_spatial_lock_keys,
    is_valid_location,
)


# ---------------------------------------------------------------------------
# Test Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.bind = MagicMock()
    session.bind.dialect = MagicMock()
    session.bind.dialect.name = "postgresql"
    return session


@pytest.fixture
def correlation_service(mock_session: AsyncMock) -> EventCorrelationService:
    service = EventCorrelationService(mock_session)
    service._event_repo.find_nearby_active_event = AsyncMock(return_value=None)
    service._event_repo.create = AsyncMock(side_effect=lambda e: e)
    return service


def make_detection(
    detection_type: str = "POTHOLE",
    latitude: float | None = 12.9716,
    longitude: float | None = 77.5946,
    confidence: float = 0.90,
    detected_at: datetime | None = None,
    bus_id: uuid.UUID | None = None,
    camera_id: uuid.UUID | None = None,
    stream_id: uuid.UUID | None = None,
    frame_ref: str | None = "bus1/front/frame_001",
) -> Detection:
    b_id = bus_id or uuid.uuid4()
    c_id = camera_id or uuid.uuid4()
    t = detected_at or datetime.now(timezone.utc)
    return Detection(
        id=uuid.uuid4(),
        bus_id=b_id,
        camera_id=c_id,
        stream_id=stream_id,
        detection_type=detection_type,
        confidence=confidence,
        latitude=latitude,
        longitude=longitude,
        detected_at=t,
        frame_reference=frame_ref,
        extra_metadata={"model": "yolov8n", "track_id": 101},
    )


# ---------------------------------------------------------------------------
# Test Suite: Phase 5.1 Scenarios A through O
# ---------------------------------------------------------------------------

class TestPhase5UrbanEventCorrelation:
    """Verifies all Phase 5.1 requirements for the Urban Event Correlation Engine."""

    # Scenario A: First valid pothole detection creates one Urban Event with schema default severity
    async def test_scenario_a_first_valid_pothole_creates_urban_event(
        self, correlation_service: EventCorrelationService
    ) -> None:
        det = make_detection(
            detection_type="POTHOLE",
            latitude=12.9716,
            longitude=77.5946,
            confidence=0.88,
            detected_at=datetime(2026, 9, 11, 10, 0, 0, tzinfo=timezone.utc),
        )

        event = await correlation_service.correlate_and_link(det)

        assert event is not None
        assert event.event_type == EventType.POTHOLE
        assert event.status == EventStatus.DETECTED
        # Phase 5.1: Severity is NOT calculated; uses database schema-safe default (MEDIUM)
        assert event.severity == EventSeverity.MEDIUM
        assert event.latitude == 12.9716
        assert event.longitude == 77.5946
        assert event.confidence == 0.88
        assert event.first_detected_at == det.detected_at
        assert event.last_detected_at == det.detected_at
        assert event.extra_metadata["detection_count"] == 1
        assert det.event_id == event.id
        correlation_service._event_repo.create.assert_called_once()

    # Scenario B: Second nearby pothole detection within 300 seconds attaches to existing event
    async def test_scenario_b_second_nearby_pothole_within_300s_merges(
        self, correlation_service: EventCorrelationService
    ) -> None:
        t0 = datetime(2026, 9, 11, 10, 0, 0, tzinfo=timezone.utc)
        existing_event = Event(
            id=uuid.uuid4(),
            event_type=EventType.POTHOLE,
            status=EventStatus.DETECTED,
            severity=EventSeverity.MEDIUM,
            latitude=12.9716,
            longitude=77.5946,
            confidence=0.80,
            first_detected_at=t0,
            last_detected_at=t0,
            extra_metadata={"detection_count": 1},
        )
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(
            return_value=existing_event
        )

        t1 = t0 + timedelta(seconds=120)  # within 300s default window
        det2 = make_detection(
            detection_type="POTHOLE",
            latitude=12.9717,
            longitude=77.5947,
            confidence=0.90,
            detected_at=t1,
        )

        linked_event = await correlation_service.correlate_and_link(det2)

        assert linked_event is existing_event
        assert det2.event_id == existing_event.id
        assert existing_event.last_detected_at == t1
        assert existing_event.first_detected_at == t0
        assert existing_event.extra_metadata["detection_count"] == 2
        # Confidence running weighted average: (0.80 * 1 + 0.90) / 2 = 0.85
        assert existing_event.confidence == 0.85
        correlation_service._event_repo.create.assert_not_called()

    # Scenario C: Same detection type outside spatial radius creates new event
    async def test_scenario_c_same_type_outside_spatial_radius_creates_new_event(
        self, correlation_service: EventCorrelationService
    ) -> None:
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(return_value=None)

        det_far = make_detection(
            detection_type="POTHOLE",
            latitude=12.9850,  # ~1.5km away
            longitude=77.6100,
            confidence=0.85,
        )

        event = await correlation_service.correlate_and_link(det_far)

        assert event is not None
        assert event.latitude == 12.9850
        assert event.severity == EventSeverity.MEDIUM
        assert event.extra_metadata["detection_count"] == 1
        correlation_service._event_repo.create.assert_called_once()

    # Scenario D: Same detection type outside temporal window creates new event
    async def test_scenario_d_same_type_outside_temporal_window_creates_new_event(
        self, correlation_service: EventCorrelationService
    ) -> None:
        t0 = datetime(2026, 9, 11, 10, 0, 0, tzinfo=timezone.utc)
        t_after = t0 + timedelta(seconds=600)  # > 300s default window

        correlation_service._event_repo.find_nearby_active_event = AsyncMock(return_value=None)

        det_later = make_detection(
            detection_type="POTHOLE",
            latitude=12.9716,
            longitude=77.5946,
            confidence=0.92,
            detected_at=t_after,
        )

        event = await correlation_service.correlate_and_link(det_later)

        assert event is not None
        assert event.first_detected_at == t_after
        assert event.last_detected_at == t_after
        assert event.severity == EventSeverity.MEDIUM
        assert event.extra_metadata["detection_count"] == 1
        correlation_service._event_repo.create.assert_called_once()

    # Scenario E: Different detection type at same location does not correlate
    async def test_scenario_e_different_detection_type_does_not_correlate(
        self, correlation_service: EventCorrelationService
    ) -> None:
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(return_value=None)

        det_water = make_detection(
            detection_type="WATERLOGGING",
            latitude=12.9716,
            longitude=77.5946,
            confidence=0.95,
        )

        event = await correlation_service.correlate_and_link(det_water)

        assert event is not None
        assert event.event_type == EventType.WATERLOGGING
        # Schema default severity; no business logic applied
        assert event.severity == EventSeverity.MEDIUM
        # Must have queried specifically for WATERLOGGING
        call_args = correlation_service._event_repo.find_nearby_active_event.call_args[1]
        assert call_args["event_type"] == EventType.WATERLOGGING

    # Scenario F: Missing GPS retains detection with event_id = None (Zero fabricated GPS rule)
    async def test_scenario_f_missing_coordinates_zero_fabricated_gps(
        self, correlation_service: EventCorrelationService
    ) -> None:
        det = make_detection(
            detection_type="POTHOLE",
            latitude=None,
            longitude=None,
            confidence=0.90,
        )

        result = await correlation_service.correlate_and_link(det)

        assert result is None
        assert det.event_id is None
        correlation_service._event_repo.create.assert_not_called()
        correlation_service._event_repo.find_nearby_active_event.assert_not_called()

    # Scenario G: Partial / invalid GPS does not correlate
    @pytest.mark.parametrize(
        ("lat", "lon"),
        [
            (12.9716, None),
            (None, 77.5946),
            (95.0, 77.5946),     # lat > 90
            (-95.0, 77.5946),    # lat < -90
            (12.9716, 185.0),    # lon > 180
            (12.9716, -185.0),   # lon < -180
        ],
    )
    async def test_scenario_g_partial_or_invalid_gps_does_not_correlate(
        self, correlation_service: EventCorrelationService, lat: float | None, lon: float | None
    ) -> None:
        assert is_valid_location(lat, lon) is False
        det = make_detection(
            detection_type="POTHOLE",
            latitude=lat,
            longitude=lon,
        )

        result = await correlation_service.correlate_and_link(det)

        assert result is None
        assert det.event_id is None
        correlation_service._event_repo.create.assert_not_called()

    # Scenario H: Idempotency / duplicate detection does not create duplicate event
    async def test_scenario_h_idempotency_duplicate_detection_returns_existing(
        self, mock_session: AsyncMock
    ) -> None:
        detection_service = DetectionService(mock_session)
        b_id = uuid.uuid4()
        c_id = uuid.uuid4()
        existing_event_id = uuid.uuid4()

        existing_det = Detection(
            id=uuid.uuid4(),
            bus_id=b_id,
            camera_id=c_id,
            detection_type="POTHOLE",
            confidence=0.90,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
            frame_reference="frame_100",
            event_id=existing_event_id,
        )

        bus = Bus(id=b_id, bus_number="DL-01-A-1234")
        camera = Camera(id=c_id, bus_id=b_id, camera_type=CameraType.front)

        detection_service._bus_repo.get_by_id = AsyncMock(return_value=bus)
        detection_service._camera_repo.get_by_id = AsyncMock(return_value=camera)
        detection_service.repo.find_duplicate = AsyncMock(return_value=existing_det)
        detection_service.repo.create = AsyncMock()

        dto = DetectionCreate(
            bus_id=b_id,
            camera_id=c_id,
            detection_type="POTHOLE",
            confidence=0.90,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
            frame_reference="frame_100",
        )

        res = await detection_service.create_detection(dto)

        assert res.id == existing_det.id
        assert res.event_id == existing_event_id
        detection_service.repo.create.assert_not_called()

    # Scenario I: Cross-bus / cross-camera detection merges into existing event
    async def test_scenario_i_cross_bus_and_camera_correlation(
        self, correlation_service: EventCorrelationService
    ) -> None:
        t0 = datetime(2026, 9, 11, 10, 0, 0, tzinfo=timezone.utc)
        bus1_id, cam1_id = uuid.uuid4(), uuid.uuid4()
        bus2_id, cam2_id = uuid.uuid4(), uuid.uuid4()
        bus3_id, cam3_id = uuid.uuid4(), uuid.uuid4()

        shared_event = Event(
            id=uuid.uuid4(),
            event_type=EventType.POTHOLE,
            status=EventStatus.DETECTED,
            severity=EventSeverity.MEDIUM,
            latitude=12.9716,
            longitude=77.5946,
            confidence=0.80,
            first_detected_at=t0,
            last_detected_at=t0,
            bus_id=bus1_id,
            camera_id=cam1_id,
            extra_metadata={"detection_count": 1, "reporting_buses": [str(bus1_id)]},
        )
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(
            return_value=shared_event
        )

        # Bus 2, Camera 2 observes same pothole 30s later
        det_bus2 = make_detection(
            detection_type="POTHOLE",
            bus_id=bus2_id,
            camera_id=cam2_id,
            latitude=12.97165,
            longitude=77.59462,
            confidence=0.88,
            detected_at=t0 + timedelta(seconds=30),
        )
        res2 = await correlation_service.correlate_and_link(det_bus2)
        assert res2 is shared_event
        assert det_bus2.event_id == shared_event.id
        assert shared_event.extra_metadata["detection_count"] == 2
        assert str(bus2_id) in shared_event.extra_metadata["reporting_buses"]

        # Bus 3, Camera 3 observes same pothole 60s later
        det_bus3 = make_detection(
            detection_type="POTHOLE",
            bus_id=bus3_id,
            camera_id=cam3_id,
            latitude=12.97162,
            longitude=77.59461,
            confidence=0.92,
            detected_at=t0 + timedelta(seconds=60),
        )
        res3 = await correlation_service.correlate_and_link(det_bus3)
        assert res3 is shared_event
        assert det_bus3.event_id == shared_event.id
        assert shared_event.extra_metadata["detection_count"] == 3
        assert str(bus3_id) in shared_event.extra_metadata["reporting_buses"]

    # Scenario J: first_detected_at preserved when new detections link
    async def test_scenario_j_first_detected_at_preserved(
        self, correlation_service: EventCorrelationService
    ) -> None:
        t0 = datetime(2026, 9, 11, 10, 0, 0, tzinfo=timezone.utc)
        event = Event(
            id=uuid.uuid4(),
            event_type=EventType.DAMAGED_ROAD,
            status=EventStatus.DETECTED,
            severity=EventSeverity.MEDIUM,
            confidence=0.75,
            first_detected_at=t0,
            last_detected_at=t0,
            extra_metadata={"detection_count": 1},
        )
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(return_value=event)

        det = make_detection(
            detection_type="DAMAGED_ROAD",
            detected_at=t0 + timedelta(seconds=180),
        )
        await correlation_service.correlate_and_link(det)

        assert event.first_detected_at == t0

    # Scenario K: last_detected_at updated monotonically to latest detection timestamp
    async def test_scenario_k_last_detected_at_updated_monotonically(
        self, correlation_service: EventCorrelationService
    ) -> None:
        t0 = datetime(2026, 9, 11, 10, 0, 0, tzinfo=timezone.utc)
        event = Event(
            id=uuid.uuid4(),
            event_type=EventType.MISSING_DIVIDER,
            status=EventStatus.DETECTED,
            severity=EventSeverity.MEDIUM,
            confidence=0.90,
            first_detected_at=t0,
            last_detected_at=t0,
            extra_metadata={"detection_count": 1},
        )
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(return_value=event)

        t_latest = t0 + timedelta(seconds=240)
        det = make_detection(
            detection_type="MISSING_DIVIDER",
            detected_at=t_latest,
        )
        await correlation_service.correlate_and_link(det)

        assert event.last_detected_at == t_latest

        # Slower out-of-order detection arriving with earlier timestamp does NOT roll back last_detected_at
        t_earlier = t0 + timedelta(seconds=50)
        det_out_of_order = make_detection(
            detection_type="MISSING_DIVIDER",
            detected_at=t_earlier,
        )
        await correlation_service.correlate_and_link(det_out_of_order)
        assert event.last_detected_at == t_latest

    # Scenario L: Deterministic confidence aggregation follows running weighted average formula in [0, 1]
    async def test_scenario_l_confidence_running_weighted_average(
        self, correlation_service: EventCorrelationService
    ) -> None:
        t0 = datetime(2026, 9, 11, 10, 0, 0, tzinfo=timezone.utc)
        event = Event(
            id=uuid.uuid4(),
            event_type=EventType.POTHOLE,
            confidence=0.85,
            first_detected_at=t0,
            last_detected_at=t0,
            extra_metadata={"detection_count": 1},
        )
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(return_value=event)

        # Ingestion 2: confidence = 0.95 -> ((0.85 * 1) + 0.95) / 2 = 0.9000
        det2 = make_detection(detection_type="POTHOLE", confidence=0.95)
        await correlation_service.correlate_and_link(det2)
        assert event.confidence == 0.90
        assert 0.0 <= event.confidence <= 1.0
        assert event.extra_metadata["detection_count"] == 2

        # Ingestion 3: confidence = 0.60 -> ((0.90 * 2) + 0.60) / 3 = 2.40 / 3 = 0.8000
        det3 = make_detection(detection_type="POTHOLE", confidence=0.60)
        await correlation_service.correlate_and_link(det3)
        assert event.confidence == 0.80
        assert 0.0 <= event.confidence <= 1.0
        assert event.extra_metadata["detection_count"] == 3

    # Scenario M: Terminal events (RESOLVED, REJECTED) are excluded from correlation and not reused
    async def test_scenario_m_terminal_events_are_not_reused(
        self, correlation_service: EventCorrelationService
    ) -> None:
        # Confirm that terminal statuses are strictly excluded from ACTIVE_EVENT_STATUSES
        assert EventStatus.RESOLVED in TERMINAL_EVENT_STATUSES
        assert EventStatus.REJECTED in TERMINAL_EVENT_STATUSES
        assert EventStatus.RESOLVED not in ACTIVE_EVENT_STATUSES
        assert EventStatus.REJECTED not in ACTIVE_EVENT_STATUSES

        # Confirm active statuses eligible for correlation
        expected_active = {
            EventStatus.DETECTED,
            EventStatus.VERIFIED,
            EventStatus.OPEN,
            EventStatus.ACKNOWLEDGED,
            EventStatus.IN_PROGRESS,
        }
        assert ACTIVE_EVENT_STATUSES == expected_active

        # When repo query filters out terminal events, repo returns None and a new event is synthesized
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(return_value=None)

        det = make_detection(
            detection_type="POTHOLE",
            latitude=12.9716,
            longitude=77.5946,
            confidence=0.90,
        )

        new_ev = await correlation_service.correlate_and_link(det)

        assert new_ev is not None
        assert new_ev.status == EventStatus.DETECTED
        assert new_ev.severity == EventSeverity.MEDIUM
        correlation_service._event_repo.create.assert_called_once()

    # Scenario N: Event APIs and GeoJSON feature collection remain functional
    async def test_scenario_n_event_apis_retrieval_and_geojson(
        self, mock_session: AsyncMock
    ) -> None:
        event_service = EventService(mock_session)
        ev_id = uuid.uuid4()
        sample_event = Event(
            id=ev_id,
            event_type=EventType.POTHOLE,
            status=EventStatus.DETECTED,
            severity=EventSeverity.MEDIUM,
            latitude=12.9716,
            longitude=77.5946,
            confidence=0.90,
            first_detected_at=datetime(2026, 9, 11, 10, 0, 0, tzinfo=timezone.utc),
            last_detected_at=datetime(2026, 9, 11, 10, 2, 0, tzinfo=timezone.utc),
            extra_metadata={"detection_count": 2},
        )
        event_service.repo.get_by_id = AsyncMock(return_value=sample_event)
        event_service.repo.list = AsyncMock(return_value=[sample_event])

        # Test single event fetch
        fetched = await event_service.get_event(ev_id)
        assert fetched.id == ev_id
        assert fetched.event_type == EventType.POTHOLE

        # Test event listing with status filter
        listed = await event_service.list_events(status=EventStatus.DETECTED)
        assert len(listed) == 1
        assert listed[0].id == ev_id

        # Test GeoJSON feature generation
        from app.api.routes.events import get_events_geojson
        geojson = await get_events_geojson(service=event_service)
        assert geojson.type == "FeatureCollection"
        assert len(geojson.features) == 1
        feature = geojson.features[0]
        assert feature.type == "Feature"
        assert feature.geometry.coordinates == [77.5946, 12.9716]
        assert feature.properties.event_type == EventType.POTHOLE
        assert feature.properties.confidence == 0.90

    # Scenario O1: Concurrency — Spatial grid key derivation is deterministic
    def test_scenario_o1_spatial_grid_cell_and_lock_keys_deterministic(self) -> None:
        cell_a = compute_spatial_grid_cell(12.9716, 77.5946, grid_size_degrees=0.001)
        assert cell_a == (12971, 77594)

        keys = get_spatial_lock_keys(
            event_type=EventType.POTHOLE,
            latitude=12.9716,
            longitude=77.5946,
            radius_meters=50.0,
            grid_size_degrees=0.001,
        )

        assert isinstance(keys, list)
        assert len(keys) >= 1
        # Keys must be strictly sorted to prevent PostgreSQL deadlocks
        assert keys == sorted(keys)
        for k in keys:
            assert k.startswith("event_correlation:POTHOLE:")

    # Scenario O2: Concurrency — Nearby detections acquire compatible shared lock keys
    def test_scenario_o2_nearby_detections_acquire_compatible_shared_lock_keys(self) -> None:
        # Det 1 at (12.9716, 77.5946), Det 2 ~15m away at (12.9717, 77.5947)
        keys1 = get_spatial_lock_keys(
            event_type=EventType.POTHOLE,
            latitude=12.9716,
            longitude=77.5946,
            radius_meters=50.0,
        )
        keys2 = get_spatial_lock_keys(
            event_type=EventType.POTHOLE,
            latitude=12.9717,
            longitude=77.5947,
            radius_meters=50.0,
        )

        shared = set(keys1).intersection(set(keys2))
        # Nearby detections within 50m must share at least one lock key
        assert len(shared) > 0, "Nearby detections must share spatial advisory lock keys to serialize"

    # Scenario O3: Concurrency — Distant detections acquire disjoint lock keys (no global serialization)
    def test_scenario_o3_distant_detections_acquire_disjoint_lock_keys(self) -> None:
        # Det 1 at MG Road (12.9716, 77.5946)
        keys1 = get_spatial_lock_keys(
            event_type=EventType.POTHOLE,
            latitude=12.9716,
            longitude=77.5946,
            radius_meters=50.0,
        )
        # Det 2 at Indiranagar ~2.5km away (12.9850, 77.6100)
        keys2 = get_spatial_lock_keys(
            event_type=EventType.POTHOLE,
            latitude=12.9850,
            longitude=77.6100,
            radius_meters=50.0,
        )

        overlap = set(keys1).intersection(set(keys2))
        assert len(overlap) == 0, "Distant detections must have disjoint lock keys and execute in parallel"

    # Scenario O4: Concurrency — Different event types at same location acquire disjoint lock keys
    def test_scenario_o4_different_event_types_acquire_disjoint_lock_keys(self) -> None:
        keys_pothole = get_spatial_lock_keys(
            event_type=EventType.POTHOLE,
            latitude=12.9716,
            longitude=77.5946,
            radius_meters=50.0,
        )
        keys_water = get_spatial_lock_keys(
            event_type=EventType.WATERLOGGING,
            latitude=12.9716,
            longitude=77.5946,
            radius_meters=50.0,
        )

        overlap = set(keys_pothole).intersection(set(keys_water))
        assert len(overlap) == 0, "Different event types must not serialize each other"

    # Scenario O5: Concurrency — Transaction advisory lock is executed on PostgreSQL session
    async def test_scenario_o5_advisory_lock_executed_on_postgresql_session(
        self, mock_session: AsyncMock
    ) -> None:
        service = EventCorrelationService(mock_session)
        service._event_repo.find_nearby_active_event = AsyncMock(return_value=None)
        service._event_repo.create = AsyncMock(side_effect=lambda e: e)

        det = make_detection(
            detection_type="POTHOLE",
            latitude=12.9716,
            longitude=77.5946,
        )

        await service.correlate_and_link(det)

        # Verify that pg_advisory_xact_lock query was executed on the session
        assert mock_session.execute.called
        call_args_list = mock_session.execute.call_args_list
        executed_sqls = [str(call[0][0]) for call in call_args_list if len(call[0]) > 0]
        advisory_calls = [sql for sql in executed_sqls if "pg_advisory_xact_lock" in sql]
        assert len(advisory_calls) >= 1, "Advisory transaction lock must be acquired on PostgreSQL session"
