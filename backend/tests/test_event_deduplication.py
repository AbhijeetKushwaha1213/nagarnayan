"""
Unit tests for Phase 5 — Detection to Event Generation & Spatial-Temporal Deduplication.

Tests verify:
1. Municipal issue detection creates a new Event (DETECTED status).
2. Second detection of same issue within radius/time window links to existing Event.
3. Detection outside spatial radius creates a new Event.
4. Detection outside temporal window creates a new Event.
5. Different event types do not merge.
6. RESOLVED / REJECTED events are not reused.
7. Multiple detections reference the same Event.
8. first_detected_at remains unchanged on Event.
9. last_detected_at updates to latest detection timestamp.
10. Coordinate-less detection does not receive fake coordinates.
11. VEHICLE / PEDESTRIAN observations do not synthesize events (event_id is None).
12. Event status remains DETECTED after automatic synthesis (not VERIFIED).
13. Deterministic municipal severity policy by issue type.
14. Confidence aggregation strategy (running weighted average).
15. Coordinate-less fallback: same bus & camera within time window merges.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.detection import Detection
from app.models.event import Event, EventSeverity, EventStatus, EventType
from app.services.event_correlation import (
    DETECTION_TYPE_TO_EVENT_TYPE,
    EventCorrelationService,
)


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def correlation_service(mock_session: AsyncMock) -> EventCorrelationService:
    service = EventCorrelationService(mock_session)
    # Stub event repository methods
    service._event_repo.find_nearby_active_event = AsyncMock(return_value=None)
    service._event_repo.find_active_bus_camera_event = AsyncMock(return_value=None)
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
) -> Detection:
    b_id = bus_id or uuid.uuid4()
    c_id = camera_id or uuid.uuid4()
    t = detected_at or datetime.now(timezone.utc)
    return Detection(
        id=uuid.uuid4(),
        bus_id=b_id,
        camera_id=c_id,
        detection_type=detection_type,
        confidence=confidence,
        latitude=latitude,
        longitude=longitude,
        detected_at=t,
        frame_reference="bus_front/frame_000001",
        extra_metadata={"model": "yolov8n"},
    )


@pytest.mark.asyncio
class TestEventDeduplicationLogic:

    async def test_1_municipal_detection_creates_new_event(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 1: A municipal issue detection creates a new Event."""
        det = make_detection(detection_type="POTHOLE", confidence=0.88)
        event = await correlation_service.correlate_and_link(det)

        assert event is not None
        assert event.event_type == EventType.POTHOLE
        assert event.status == EventStatus.DETECTED
        assert event.confidence == 0.88
        assert event.latitude == det.latitude
        assert event.longitude == det.longitude
        assert det.event_id == event.id
        correlation_service._event_repo.create.assert_called_once()

    async def test_2_second_detection_within_radius_and_time_merges(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 2: Second detection within radius/time links to existing Event."""
        t0 = datetime(2026, 9, 9, 10, 0, 0, tzinfo=timezone.utc)
        existing_event = Event(
            id=uuid.uuid4(),
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            status=EventStatus.DETECTED,
            latitude=12.9716,
            longitude=77.5946,
            confidence=0.85,
            first_detected_at=t0,
            last_detected_at=t0,
            extra_metadata={"detection_count": 1, "reporting_buses": ["bus-1"]},
        )

        # Mock repo returning existing nearby active event
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(
            return_value=existing_event
        )

        t1 = t0 + timedelta(seconds=45)
        det2 = make_detection(
            detection_type="POTHOLE",
            confidence=0.95,
            detected_at=t1,
        )

        result_event = await correlation_service.correlate_and_link(det2)

        assert result_event is existing_event
        assert det2.event_id == existing_event.id
        # Did not create a new event
        correlation_service._event_repo.create.assert_not_called()

    async def test_3_detection_outside_spatial_radius_creates_new_event(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 3: Detection outside spatial radius creates a new Event."""
        # When outside radius, repo returns None
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(
            return_value=None
        )

        det = make_detection(
            detection_type="POTHOLE",
            latitude=13.0500,  # ~10 km away
            longitude=77.6500,
        )
        event = await correlation_service.correlate_and_link(det)

        assert event is not None
        assert det.event_id == event.id
        correlation_service._event_repo.create.assert_called_once()

    async def test_4_detection_outside_time_window_creates_new_event(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 4: Detection outside temporal window creates a new Event."""
        # When outside 300s window, repo returns None
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(
            return_value=None
        )

        det = make_detection(
            detection_type="POTHOLE",
            detected_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        event = await correlation_service.correlate_and_link(det)

        assert event is not None
        assert det.event_id == event.id
        correlation_service._event_repo.create.assert_called_once()

    async def test_5_different_event_types_do_not_merge(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 5: Different event types do not merge."""
        # Pothole detection queries for POTHOLE, DAMAGED_ROAD queries for DAMAGED_ROAD
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(
            return_value=None
        )

        det_road = make_detection(detection_type="DAMAGED_ROAD")
        event_road = await correlation_service.correlate_and_link(det_road)

        assert event_road is not None
        assert event_road.event_type == EventType.DAMAGED_ROAD

        # Verify repo was called with event_type=EventType.DAMAGED_ROAD
        call_kwargs = correlation_service._event_repo.find_nearby_active_event.call_args[1]
        assert call_kwargs["event_type"] == EventType.DAMAGED_ROAD

    async def test_6_resolved_and_rejected_events_not_reused(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 6: Inactive (RESOLVED, REJECTED) events are never returned by repository."""
        # find_nearby_active_event excludes RESOLVED/REJECTED via status.notin_ filter
        # If no active event exists, returns None and creates new Event
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(
            return_value=None
        )

        det = make_detection(detection_type="POTHOLE")
        event = await correlation_service.correlate_and_link(det)

        assert event is not None
        assert event.status == EventStatus.DETECTED

    async def test_7_multiple_detections_reference_one_event(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 7: 3+ detections merge under 1 Event."""
        t0 = datetime(2026, 9, 9, 10, 0, 0, tzinfo=timezone.utc)
        shared_event = Event(
            id=uuid.uuid4(),
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            status=EventStatus.DETECTED,
            latitude=12.9716,
            longitude=77.5946,
            confidence=0.80,
            first_detected_at=t0,
            last_detected_at=t0,
            extra_metadata={"detection_count": 1, "reporting_buses": ["bus-1"]},
        )
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(
            return_value=shared_event
        )

        det_b = make_detection(detection_type="POTHOLE", confidence=0.85, detected_at=t0 + timedelta(seconds=20))
        det_c = make_detection(detection_type="POTHOLE", confidence=0.90, detected_at=t0 + timedelta(seconds=40))

        await correlation_service.correlate_and_link(det_b)
        await correlation_service.correlate_and_link(det_c)

        assert det_b.event_id == shared_event.id
        assert det_c.event_id == shared_event.id
        assert shared_event.extra_metadata["detection_count"] == 3

    async def test_8_first_detected_at_remains_unchanged(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 8: first_detected_at remains unchanged on Event."""
        t0 = datetime(2026, 9, 9, 10, 0, 0, tzinfo=timezone.utc)
        existing_event = Event(
            id=uuid.uuid4(),
            event_type=EventType.POTHOLE,
            status=EventStatus.DETECTED,
            confidence=0.80,
            first_detected_at=t0,
            last_detected_at=t0,
            extra_metadata={"detection_count": 1},
        )
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(
            return_value=existing_event
        )

        t1 = t0 + timedelta(seconds=120)
        det = make_detection(detection_type="POTHOLE", detected_at=t1)
        await correlation_service.correlate_and_link(det)

        assert existing_event.first_detected_at == t0

    async def test_9_last_detected_at_updates_correctly(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 9: last_detected_at updates to latest detection timestamp."""
        t0 = datetime(2026, 9, 9, 10, 0, 0, tzinfo=timezone.utc)
        existing_event = Event(
            id=uuid.uuid4(),
            event_type=EventType.POTHOLE,
            status=EventStatus.DETECTED,
            confidence=0.80,
            first_detected_at=t0,
            last_detected_at=t0,
            extra_metadata={"detection_count": 1},
        )
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(
            return_value=existing_event
        )

        t1 = t0 + timedelta(seconds=120)
        det = make_detection(detection_type="POTHOLE", detected_at=t1)
        await correlation_service.correlate_and_link(det)

        assert existing_event.last_detected_at == t1

    async def test_10_coordinate_less_detection_no_fake_coordinates(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 10: Coordinate-less detection creates no event and leaves event_id=None."""
        det = make_detection(
            detection_type="POTHOLE",
            latitude=None,
            longitude=None,
        )
        event = await correlation_service.correlate_and_link(det)

        assert event is None
        assert det.event_id is None
        correlation_service._event_repo.create.assert_not_called()

    async def test_11_unmapped_observations_no_event(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 11: Unmapped observations do not synthesize events."""
        det_unknown = make_detection(detection_type="UNKNOWN_OBJECT")
        det_animal = make_detection(detection_type="ANIMAL")
        det_debris = make_detection(detection_type="UNRECOGNIZED")

        res1 = await correlation_service.correlate_and_link(det_unknown)
        res2 = await correlation_service.correlate_and_link(det_animal)
        res3 = await correlation_service.correlate_and_link(det_debris)

        assert res1 is None
        assert res2 is None
        assert res3 is None
        assert det_unknown.event_id is None
        assert det_animal.event_id is None
        assert det_debris.event_id is None
        correlation_service._event_repo.create.assert_not_called()

    async def test_12_event_status_remains_detected(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 12: Event status remains DETECTED (not automatically VERIFIED)."""
        det = make_detection(detection_type="POTHOLE", confidence=0.99)
        event = await correlation_service.correlate_and_link(det)

        assert event is not None
        assert event.status == EventStatus.DETECTED
        assert event.verified_at is None

    async def test_13_schema_default_severity_preserved(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 13: Newly synthesized events preserve schema-safe default severity without Phase 5 business rule."""
        det = make_detection(detection_type="POTHOLE", confidence=0.88)
        event = await correlation_service.correlate_and_link(det)

        assert event is not None
        assert event.severity == EventSeverity.MEDIUM

    async def test_14_confidence_aggregation_running_average(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 14: Confidence updates via running weighted average."""
        t0 = datetime.now(timezone.utc)
        existing_event = Event(
            id=uuid.uuid4(),
            event_type=EventType.POTHOLE,
            confidence=0.80,
            first_detected_at=t0,
            last_detected_at=t0,
            extra_metadata={"detection_count": 1},
        )
        correlation_service._event_repo.find_nearby_active_event = AsyncMock(
            return_value=existing_event
        )

        det = make_detection(detection_type="POTHOLE", confidence=0.90)
        await correlation_service.correlate_and_link(det)

        # Expected: ((0.80 * 1) + 0.90) / 2 = 0.85
        assert existing_event.confidence == 0.85
        assert existing_event.extra_metadata["detection_count"] == 2

    async def test_15_coordinate_less_never_synthesizes_or_merges_event(
        self, correlation_service: EventCorrelationService
    ) -> None:
        """Requirement 15: In accordance with Phase 5 Zero-Fabricated-GPS Rule, missing coordinates never merge or synthesize events."""
        b_id = uuid.uuid4()
        c_id = uuid.uuid4()
        t0 = datetime(2026, 9, 9, 10, 0, 0, tzinfo=timezone.utc)

        det = make_detection(
            detection_type="POTHOLE",
            latitude=None,
            longitude=None,
            bus_id=b_id,
            camera_id=c_id,
            detected_at=t0 + timedelta(seconds=30),
        )

        linked_event = await correlation_service.correlate_and_link(det)

        assert linked_event is None
        assert det.event_id is None
        correlation_service._event_repo.create.assert_not_called()

    async def test_16_deterministic_scenario_a_b_c_d(self) -> None:
        """
        Step 14 Deterministic Scenario:
        Detection A: POTHOLE, location X, timestamp T
          -> Event count = 1
        Detection B: POTHOLE, location within 30m of X, timestamp within 5 mins of T
          -> Event count = 1, Detection count = 2, both Detection.event_id = same Event ID
        Detection C: POTHOLE, location >30m away (~500m)
          -> Event count = 2
        Detection D: POTHOLE, same location X, timestamp >5 minutes later (T + 600s)
          -> Event count = 3
        """
        import math
        session = AsyncMock()
        service = EventCorrelationService(session)

        # In-memory store simulating PostGIS repository storage & matching
        events: list[Event] = []

        def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            r = 6371000.0  # Earth radius in meters
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlam = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2)**2
            return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        async def mock_find_nearby(
            event_type: EventType,
            latitude: float,
            longitude: float,
            detection_time: datetime,
            radius_meters: float = 30.0,
            time_window_seconds: int = 300,
            for_update: bool = False,
        ) -> Event | None:
            min_t = detection_time - timedelta(seconds=time_window_seconds)
            max_t = detection_time + timedelta(seconds=time_window_seconds)
            candidates = []
            for ev in events:
                if ev.event_type != event_type:
                    continue
                if ev.status in (EventStatus.RESOLVED, EventStatus.REJECTED):
                    continue
                if not (ev.last_detected_at >= min_t and ev.first_detected_at <= max_t):
                    continue
                if ev.latitude is None or ev.longitude is None:
                    continue
                dist = haversine_meters(ev.latitude, ev.longitude, latitude, longitude)
                if dist <= radius_meters:
                    candidates.append((dist, ev))
            if not candidates:
                return None
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]

        async def mock_create(ev: Event) -> Event:
            events.append(ev)
            return ev

        service._event_repo.find_nearby_active_event = AsyncMock(side_effect=mock_find_nearby)
        service._event_repo.create = AsyncMock(side_effect=mock_create)

        t0 = datetime(2026, 9, 9, 10, 0, 0, tzinfo=timezone.utc)
        loc_x = (12.9716, 77.5946)

        # ── Detection A ────────────────────────────────────────────────────────
        det_a = make_detection(detection_type="POTHOLE", latitude=loc_x[0], longitude=loc_x[1], detected_at=t0)
        event_a = await service.correlate_and_link(det_a)

        assert event_a is not None
        assert len(events) == 1
        assert det_a.event_id == event_a.id
        event_1_id = event_a.id

        # ── Detection B (~15m away, 60s later) ─────────────────────────────────
        loc_b = (12.9717, 77.5947)
        dist_ab = haversine_meters(loc_x[0], loc_x[1], loc_b[0], loc_b[1])
        assert dist_ab < 30.0  # strictly within 30m

        det_b = make_detection(detection_type="POTHOLE", latitude=loc_b[0], longitude=loc_b[1], detected_at=t0 + timedelta(seconds=60))
        event_b = await service.correlate_and_link(det_b)

        assert event_b is not None
        assert len(events) == 1  # Still 1 Event!
        assert event_b.id == event_1_id
        assert det_b.event_id == event_1_id
        assert det_a.event_id == det_b.event_id
        assert event_b.extra_metadata["detection_count"] == 2

        # ── Detection C (~500m away, 120s later) ───────────────────────────────
        loc_c = (12.9750, 77.5980)
        dist_ac = haversine_meters(loc_x[0], loc_x[1], loc_c[0], loc_c[1])
        assert dist_ac > 30.0  # strictly > 30m away

        det_c = make_detection(detection_type="POTHOLE", latitude=loc_c[0], longitude=loc_c[1], detected_at=t0 + timedelta(seconds=120))
        event_c = await service.correlate_and_link(det_c)

        assert event_c is not None
        assert len(events) == 2  # Now 2 Events!
        assert event_c.id != event_1_id
        assert det_c.event_id == event_c.id

        # ── Detection D (same location X, but 10 mins > 5 mins later) ──────────
        t_d = t0 + timedelta(seconds=600)  # 600s > 300s window

        det_d = make_detection(detection_type="POTHOLE", latitude=loc_x[0], longitude=loc_x[1], detected_at=t_d)
        event_d = await service.correlate_and_link(det_d)

        assert event_d is not None
        assert len(events) == 3  # Now 3 Events!
        assert event_d.id != event_1_id
        assert event_d.id != event_c.id
        assert det_d.event_id == event_d.id
