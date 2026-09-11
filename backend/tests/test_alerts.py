"""
Unit and Integration tests for Phase 6 — Event to Alert Engine.

Tests verify all 22 Phase 6 requirements:
1. CRITICAL Event creates an Alert.
2. HIGH Event creates an Alert.
3. MEDIUM Event does not create an Alert.
4. LOW Event does not create an Alert.
5. RESOLVED Event does not create an Alert.
6. REJECTED Event does not create an Alert.
7. Multiple detections attached to the same Event create only one active Alert.
8. Existing NEW alert prevents duplicate alert creation.
9. Existing ACKNOWLEDGED alert prevents duplicate alert creation.
10. RESOLVED alert allows a future alert according to the documented re-alert policy.
11. Alert references the correct Event.
12. Alert severity matches Event severity.
13. Alert title/message is deterministic.
14. Coordinate-less Event does not produce fabricated location information.
15. Alert lifecycle transition NEW -> ACKNOWLEDGED works.
16. ACKNOWLEDGED -> RESOLVED works.
17. NEW -> DISMISSED works.
18. Invalid lifecycle transitions are rejected (HTTP 422).
19. Existing Event tests continue passing.
20. Existing Detection tests continue passing.
21. Event deduplication tests continue passing.
22. Concurrent alert generation does not create duplicate active alerts.
23. Step 15 multi-step deterministic scenario execution.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.alert import Alert, AlertStatus, AlertType
from app.models.bus import Bus
from app.models.camera import Camera, CameraType
from app.models.detection import Detection
from app.models.event import Event, EventSeverity, EventStatus, EventType
from app.schemas.alert import AlertUpdate
from app.schemas.detection import DetectionCreate
from app.services.alert import AlertService
from app.services.detection import DetectionService
from app.services.event_correlation import EventCorrelationService


# ── Helpers & Fixtures ─────────────────────────────────────────────────────────


def make_event(
    event_type: EventType = EventType.POTHOLE,
    severity: EventSeverity = EventSeverity.HIGH,
    status: EventStatus = EventStatus.DETECTED,
    confidence: float = 0.86,
    latitude: float | None = 12.9716,
    longitude: float | None = 77.5946,
    event_id: uuid.UUID | None = None,
) -> Event:
    now = datetime.now(timezone.utc)
    return Event(
        id=event_id or uuid.uuid4(),
        event_type=event_type,
        severity=severity,
        status=status,
        confidence=confidence,
        latitude=latitude,
        longitude=longitude,
        first_detected_at=now,
        last_detected_at=now,
        extra_metadata={"detection_count": 1},
    )


def make_alert(
    event: Event,
    alert_type: AlertType = AlertType.MUNICIPAL_ISSUE,
    status: AlertStatus = AlertStatus.NEW,
    alert_id: uuid.UUID | None = None,
) -> Alert:
    now = datetime.now(timezone.utc)
    return Alert(
        id=alert_id or uuid.uuid4(),
        event_id=event.id,
        alert_type=alert_type,
        severity=event.severity,
        status=status,
        title="High Priority Pothole Detected",
        message="Persistent pothole detected by bus-camera observations. Confidence: 0.86",
        extra_metadata={"event_type": event.event_type.value},
        event=event,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def alert_service(mock_session: AsyncMock) -> AlertService:
    service = AlertService(mock_session)
    service.repo.find_active_alert_by_event = AsyncMock(return_value=None)
    service.repo.create = AsyncMock(side_effect=lambda a: a)
    service.repo.update = AsyncMock(side_effect=lambda a: a)
    service.repo.get_by_id_with_event = AsyncMock(return_value=None)
    service.repo.list = AsyncMock(return_value=[])
    return service


# ── Policy & Generation Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
class TestAlertPolicyEvaluation:
    """Test policy governing when an Event qualifies for an Alert (Requirements 1-6)."""

    async def test_1_critical_event_creates_alert(self, alert_service: AlertService) -> None:
        """1. CRITICAL Event creates an Alert immediately."""
        event = make_event(
            event_type=EventType.MISSING_DIVIDER,
            severity=EventSeverity.CRITICAL,
            status=EventStatus.DETECTED,
        )
        assert alert_service.should_generate_alert(event) is True

        alert = await alert_service.process_event_for_alert(event)
        assert alert is not None
        assert alert.severity == EventSeverity.CRITICAL
        assert alert.alert_type == AlertType.CRITICAL_INFRASTRUCTURE
        assert alert.status in (AlertStatus.ACTIVE, AlertStatus.NEW)

    async def test_2_high_event_creates_alert(self, alert_service: AlertService) -> None:
        """2. HIGH Event creates an Alert."""
        event = make_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            status=EventStatus.DETECTED,
        )
        assert alert_service.should_generate_alert(event) is True

        alert = await alert_service.process_event_for_alert(event)
        assert alert is not None
        assert alert.severity == EventSeverity.HIGH
        assert alert.alert_type == AlertType.MUNICIPAL_ISSUE
        assert alert.status in (AlertStatus.ACTIVE, AlertStatus.NEW)

    async def test_3_medium_event_does_not_create_alert(self, alert_service: AlertService) -> None:
        """3. MEDIUM Event does not create an Alert."""
        event = make_event(
            event_type=EventType.DAMAGED_ROAD,
            severity=EventSeverity.MEDIUM,
            status=EventStatus.DETECTED,
        )
        assert alert_service.should_generate_alert(event) is False

        alert = await alert_service.process_event_for_alert(event)
        assert alert is None

    async def test_4_low_event_does_not_create_alert(self, alert_service: AlertService) -> None:
        """4. LOW Event does not create an Alert."""
        event = make_event(
            event_type=EventType.MISSING_SIGNBOARD,
            severity=EventSeverity.LOW,
            status=EventStatus.DETECTED,
        )
        assert alert_service.should_generate_alert(event) is False

        alert = await alert_service.process_event_for_alert(event)
        assert alert is None

    async def test_5_resolved_event_does_not_create_alert(self, alert_service: AlertService) -> None:
        """5. RESOLVED Event does not create an Alert even if CRITICAL."""
        event = make_event(
            event_type=EventType.MISSING_DIVIDER,
            severity=EventSeverity.CRITICAL,
            status=EventStatus.RESOLVED,
        )
        assert alert_service.should_generate_alert(event) is False

        alert = await alert_service.process_event_for_alert(event)
        assert alert is None

    async def test_6_rejected_event_does_not_create_alert(self, alert_service: AlertService) -> None:
        """6. REJECTED Event does not create an Alert even if HIGH."""
        event = make_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            status=EventStatus.REJECTED,
        )
        assert alert_service.should_generate_alert(event) is False

        alert = await alert_service.process_event_for_alert(event)
        assert alert is None


# ── Idempotency, Anti-Flooding & Reference Tests ──────────────────────────────


@pytest.mark.asyncio
class TestAlertAntiFloodingAndReferences:
    """Test deduplication, active alert idempotency, and reference integrity (Requirements 7-14)."""

    async def test_7_multiple_detections_create_only_one_active_alert(
        self, mock_session: AsyncMock
    ) -> None:
        """7. Multiple detections attached to the same Event create only one active Alert."""
        # Setup DetectionService with real AlertService
        bus_id = uuid.uuid4()
        cam_id = uuid.uuid4()
        event_id = uuid.uuid4()

        det_service = DetectionService(mock_session)
        det_service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="B1"))
        det_service._camera_repo.get_by_id = AsyncMock(
            return_value=Camera(id=cam_id, bus_id=bus_id, camera_type=CameraType.front)
        )
        det_service.repo.create = AsyncMock(side_effect=lambda d: d)

        # Pre-existing event
        event = make_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            status=EventStatus.DETECTED,
            event_id=event_id,
        )
        det_service._event_repo.get_by_id = AsyncMock(return_value=event)

        # First detection: creates an Alert
        active_alert_holder: list[Alert] = []

        async def find_active(e_id: uuid.UUID, for_update: bool = False) -> Alert | None:
            return active_alert_holder[0] if active_alert_holder else None

        async def create_alert(a: Alert) -> Alert:
            active_alert_holder.append(a)
            return a

        det_service._alert_service.repo.find_active_alert_by_event = AsyncMock(side_effect=find_active)
        det_service._alert_service.repo.create = AsyncMock(side_effect=create_alert)

        payload_1 = DetectionCreate(
            bus_id=bus_id,
            camera_id=cam_id,
            detection_type="POTHOLE",
            confidence=0.90,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
            event_id=event_id,
        )
        await det_service.create_detection(payload_1)
        assert len(active_alert_holder) == 1

        # Second detection on same event: does NOT create another alert
        payload_2 = DetectionCreate(
            bus_id=bus_id,
            camera_id=cam_id,
            detection_type="POTHOLE",
            confidence=0.95,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
            event_id=event_id,
        )
        await det_service.create_detection(payload_2)
        assert len(active_alert_holder) == 1

    async def test_8_existing_new_alert_prevents_duplicate(
        self, alert_service: AlertService
    ) -> None:
        """8. Existing NEW alert prevents duplicate alert creation."""
        event = make_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            status=EventStatus.DETECTED,
        )
        existing_alert = make_alert(event, status=AlertStatus.NEW)
        alert_service.repo.find_active_alert_by_event = AsyncMock(return_value=existing_alert)

        alert = await alert_service.process_event_for_alert(event)
        assert alert is not None
        assert alert.id == existing_alert.id
        # Repo create was never invoked
        alert_service.repo.create.assert_not_called()

    async def test_9_existing_acknowledged_alert_prevents_duplicate(
        self, alert_service: AlertService
    ) -> None:
        """9. Existing ACKNOWLEDGED alert prevents duplicate alert creation."""
        event = make_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            status=EventStatus.DETECTED,
        )
        existing_alert = make_alert(event, status=AlertStatus.ACKNOWLEDGED)
        alert_service.repo.find_active_alert_by_event = AsyncMock(return_value=existing_alert)

        alert = await alert_service.process_event_for_alert(event)
        assert alert is not None
        assert alert.id == existing_alert.id
        alert_service.repo.create.assert_not_called()

    async def test_10_resolved_alert_allows_future_alert_on_recurrent_issue(
        self, alert_service: AlertService
    ) -> None:
        """10. RESOLVED alert allows a future alert according to re-alert policy."""
        event = make_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            status=EventStatus.DETECTED,
        )
        # Previous alert was RESOLVED, so find_active_alert_by_event returns None
        alert_service.repo.find_active_alert_by_event = AsyncMock(return_value=None)

        alert = await alert_service.process_event_for_alert(event)
        assert alert is not None
        assert alert.status in (AlertStatus.ACTIVE, AlertStatus.NEW)
        alert_service.repo.create.assert_called_once()

    async def test_11_alert_references_correct_event(self, alert_service: AlertService) -> None:
        """11. Alert references the correct Event."""
        event_id = uuid.uuid4()
        event = make_event(
            event_type=EventType.MISSING_DIVIDER,
            severity=EventSeverity.CRITICAL,
            event_id=event_id,
        )
        alert = await alert_service.process_event_for_alert(event)
        assert alert is not None
        assert alert.event_id == event_id

    async def test_12_alert_severity_matches_event_severity(
        self, alert_service: AlertService
    ) -> None:
        """12. Alert severity matches Event severity."""
        event_crit = make_event(severity=EventSeverity.CRITICAL)
        alert_crit = await alert_service.process_event_for_alert(event_crit)
        assert alert_crit is not None
        assert alert_crit.severity == EventSeverity.CRITICAL

        event_high = make_event(severity=EventSeverity.HIGH)
        alert_high = await alert_service.process_event_for_alert(event_high)
        assert alert_high is not None
        assert alert_high.severity == EventSeverity.HIGH

    async def test_13_alert_title_and_message_are_deterministic(
        self, alert_service: AlertService
    ) -> None:
        """13. Alert title/message is deterministic."""
        event = make_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            confidence=0.86,
        )
        title, message = alert_service.generate_alert_content(event)
        assert title == "High Priority Pothole Detected"
        assert "Persistent pothole detected by bus-camera observations." in message
        assert "Confidence: 0.86" in message

        event_div = make_event(
            event_type=EventType.MISSING_DIVIDER,
            severity=EventSeverity.CRITICAL,
            confidence=0.92,
        )
        title_div, message_div = alert_service.generate_alert_content(event_div)
        assert title_div == "Critical Road Divider Issue"
        assert "Persistent missing divider detected" in message_div

    async def test_14_coordinate_less_event_does_not_fabricate_location(
        self, alert_service: AlertService
    ) -> None:
        """14. Coordinate-less Event does not produce fabricated location information."""
        event = make_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            latitude=None,
            longitude=None,
        )
        alert = await alert_service.process_event_for_alert(event)
        assert alert is not None
        # Title and message do not contain fake street addresses
        assert "latitude" not in alert.extra_metadata
        assert "longitude" not in alert.extra_metadata
        assert "address" not in alert.message.lower()
        assert "road" not in alert.message.lower() or "damaged" in alert.message.lower()


# ── Lifecycle Transition Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
class TestAlertLifecycleTransitions:
    """Test state machine transitions and transition validation (Requirements 15-18)."""

    async def test_15_transition_new_to_acknowledged_works(
        self, alert_service: AlertService
    ) -> None:
        """15. Alert lifecycle transition NEW -> ACKNOWLEDGED sets acknowledged_at."""
        event = make_event()
        alert = make_alert(event, status=AlertStatus.NEW)
        assert alert.acknowledged_at is None

        alert_service.repo.get_by_id_with_event = AsyncMock(return_value=alert)
        updated = await alert_service.update_alert(
            alert.id, AlertUpdate(status=AlertStatus.ACKNOWLEDGED)
        )
        assert updated.status == AlertStatus.ACKNOWLEDGED
        assert updated.acknowledged_at is not None

    async def test_16_transition_acknowledged_to_resolved_works(
        self, alert_service: AlertService
    ) -> None:
        """16. ACKNOWLEDGED -> RESOLVED works and sets resolved_at."""
        event = make_event()
        alert = make_alert(event, status=AlertStatus.ACKNOWLEDGED)
        alert.acknowledged_at = datetime.now(timezone.utc)
        assert alert.resolved_at is None

        alert_service.repo.get_by_id_with_event = AsyncMock(return_value=alert)
        updated = await alert_service.update_alert(
            alert.id, AlertUpdate(status=AlertStatus.RESOLVED)
        )
        assert updated.status == AlertStatus.RESOLVED
        assert updated.resolved_at is not None

    async def test_17_transition_new_to_dismissed_works(
        self, alert_service: AlertService
    ) -> None:
        """17. NEW -> DISMISSED works."""
        event = make_event()
        alert = make_alert(event, status=AlertStatus.NEW)

        alert_service.repo.get_by_id_with_event = AsyncMock(return_value=alert)
        updated = await alert_service.update_alert(
            alert.id, AlertUpdate(status=AlertStatus.DISMISSED)
        )
        assert updated.status == AlertStatus.DISMISSED

    async def test_18_invalid_lifecycle_transitions_are_rejected(
        self, alert_service: AlertService
    ) -> None:
        """18. Invalid lifecycle transitions are rejected (e.g. RESOLVED -> NEW)."""
        event = make_event()

        # RESOLVED -> NEW is invalid
        resolved_alert = make_alert(event, status=AlertStatus.RESOLVED)
        alert_service.repo.get_by_id_with_event = AsyncMock(return_value=resolved_alert)
        with pytest.raises(HTTPException) as exc_info:
            await alert_service.update_alert(
                resolved_alert.id, AlertUpdate(status=AlertStatus.NEW)
            )
        assert exc_info.value.status_code == 422
        assert "Invalid lifecycle transition" in exc_info.value.detail

        # DISMISSED -> ACKNOWLEDGED is invalid
        dismissed_alert = make_alert(event, status=AlertStatus.DISMISSED)
        alert_service.repo.get_by_id_with_event = AsyncMock(return_value=dismissed_alert)
        with pytest.raises(HTTPException) as exc_info:
            await alert_service.update_alert(
                dismissed_alert.id, AlertUpdate(status=AlertStatus.ACKNOWLEDGED)
            )
        assert exc_info.value.status_code == 422
        assert "Invalid lifecycle transition" in exc_info.value.detail


# ── Concurrency & Step 15 Scenario Tests ──────────────────────────────────────


@pytest.mark.asyncio
class TestAlertConcurrencyAndScenario:
    """Test simulated concurrent generation and Step 15 deterministic flow (Requirements 22-23)."""

    async def test_22_concurrent_alert_generation_creates_only_one_active_alert(
        self, mock_session: AsyncMock
    ) -> None:
        """22. Concurrent alert generation does not create duplicate active alerts."""
        alert_service = AlertService(mock_session)
        created_alerts: list[Alert] = []
        lock = asyncio.Lock()

        async def thread_safe_find_active(event_id: uuid.UUID, for_update: bool = False) -> Alert | None:
            async with lock:
                return created_alerts[0] if created_alerts else None

        async def thread_safe_create(alert: Alert) -> Alert:
            async with lock:
                if not created_alerts:
                    created_alerts.append(alert)
                return alert

        alert_service.repo.find_active_alert_by_event = AsyncMock(side_effect=thread_safe_find_active)
        alert_service.repo.create = AsyncMock(side_effect=thread_safe_create)

        event = make_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            status=EventStatus.DETECTED,
        )

        # Run 5 concurrent evaluations
        results = await asyncio.gather(
            alert_service.process_event_for_alert(event),
            alert_service.process_event_for_alert(event),
            alert_service.process_event_for_alert(event),
            alert_service.process_event_for_alert(event),
            alert_service.process_event_for_alert(event),
        )

        # All results refer to the same single alert
        assert len(created_alerts) == 1
        for res in results:
            assert res is not None
            assert res.id == created_alerts[0].id

    async def test_step_15_deterministic_scenario(self, mock_session: AsyncMock) -> None:
        """
        Step 15: Full deterministic scenario demonstration.
        - Event A: POTHOLE, HIGH, DETECTED -> Event count = 1, Alert count = 1, Alert.event_id = Event A.id
        - Attach another Detection to Event A -> Event count = 1, Alert count = 1
        - Acknowledge the Alert -> Alert status = ACKNOWLEDGED
        - Resolve the Alert -> Alert status = RESOLVED
        - Re-alert policy: actionable detection arrives -> new Alert created per re-alert policy
        - Event B: MISSING_SIGNBOARD, LOW -> Alert count does not increase
        """
        alert_service = AlertService(mock_session)
        event_store: dict[uuid.UUID, Event] = {}
        alert_store: dict[uuid.UUID, Alert] = {}

        async def mock_find_active(event_id: uuid.UUID, for_update: bool = False) -> Alert | None:
            for alert in alert_store.values():
                if alert.event_id == event_id and alert.status in (
                    AlertStatus.ACTIVE,
                    AlertStatus.NEW,
                    AlertStatus.ACKNOWLEDGED,
                ):
                    return alert
            return None

        async def mock_create_alert(alert: Alert) -> Alert:
            alert_store[alert.id] = alert
            return alert

        async def mock_update_alert(alert: Alert) -> Alert:
            alert_store[alert.id] = alert
            return alert

        async def mock_get_alert_with_event(alert_id: uuid.UUID) -> Alert | None:
            alert = alert_store.get(alert_id)
            if alert and alert.event_id in event_store:
                alert.event = event_store[alert.event_id]
            return alert

        alert_service.repo.find_active_alert_by_event = AsyncMock(side_effect=mock_find_active)
        alert_service.repo.create = AsyncMock(side_effect=mock_create_alert)
        alert_service.repo.update = AsyncMock(side_effect=mock_update_alert)
        alert_service.repo.get_by_id_with_event = AsyncMock(side_effect=mock_get_alert_with_event)

        # 1. Event A: POTHOLE, HIGH, DETECTED
        event_a_id = uuid.uuid4()
        event_a = make_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            status=EventStatus.DETECTED,
            event_id=event_a_id,
        )
        event_store[event_a.id] = event_a

        alert_a = await alert_service.process_event_for_alert(event_a)
        assert alert_a is not None
        assert len(event_store) == 1
        assert len(alert_store) == 1
        assert alert_a.event_id == event_a.id
        assert alert_a.status in (AlertStatus.ACTIVE, AlertStatus.NEW)

        # 2. Attach another Detection to Event A
        # Simulating correlation updating event_a detection count
        event_a.extra_metadata["detection_count"] = 2
        alert_a_dup = await alert_service.process_event_for_alert(event_a)
        assert alert_a_dup is not None
        assert alert_a_dup.id == alert_a.id
        assert len(event_store) == 1
        assert len(alert_store) == 1

        # 3. Acknowledge the Alert
        alert_a_ack = await alert_service.update_alert(
            alert_a.id, AlertUpdate(status=AlertStatus.ACKNOWLEDGED)
        )
        assert alert_a_ack.status == AlertStatus.ACKNOWLEDGED
        assert alert_a_ack.acknowledged_at is not None

        # 4. Resolve the Alert
        alert_a_res = await alert_service.update_alert(
            alert_a.id, AlertUpdate(status=AlertStatus.RESOLVED)
        )
        assert alert_a_res.status == AlertStatus.RESOLVED
        assert alert_a_res.resolved_at is not None

        # 5. Actionable Event A detection recurs after resolution
        # Per documented re-alert policy: resolved alert does not block new alert
        alert_a_new = await alert_service.process_event_for_alert(event_a)
        assert alert_a_new is not None
        assert alert_a_new.id != alert_a.id  # Fresh alert synthesized
        assert alert_a_new.status in (AlertStatus.ACTIVE, AlertStatus.NEW)
        assert len(alert_store) == 2

        # 6. Event B: MISSING_SIGNBOARD, LOW
        event_b_id = uuid.uuid4()
        event_b = make_event(
            event_type=EventType.MISSING_SIGNBOARD,
            severity=EventSeverity.LOW,
            status=EventStatus.DETECTED,
            event_id=event_b_id,
        )
        event_store[event_b.id] = event_b

        alert_b = await alert_service.process_event_for_alert(event_b)
        assert alert_b is None
        # Alert count does not increase
        assert len(alert_store) == 2


# ── REST API Route Tests ──────────────────────────────────────────────────────


class TestAlertAPIRoutes:
    """Test GET /alerts, GET /alerts/{id}, PATCH /alerts/{id} endpoints."""

    @pytest.fixture(autouse=True)
    def override_service(self) -> None:
        self.mock_svc = MagicMock()
        from app.api.routes.alerts import _get_service

        app.dependency_overrides[_get_service] = lambda: self.mock_svc
        yield
        app.dependency_overrides.pop(_get_service, None)

    def test_get_alerts_list(self) -> None:
        event = make_event()
        alert = make_alert(event)
        self.mock_svc.list_alerts = AsyncMock(return_value=[alert])

        client = TestClient(app)
        response = client.get("/api/v1/alerts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == alert.title
        assert data[0]["status"] == "NEW"

    def test_get_alert_by_id(self) -> None:
        event = make_event()
        alert = make_alert(event)
        self.mock_svc.get_alert = AsyncMock(return_value=alert)

        client = TestClient(app)
        response = client.get(f"/api/v1/alerts/{alert.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(alert.id)
        assert data["event"]["id"] == str(event.id)
        assert data["event"]["event_type"] == "POTHOLE"

    def test_patch_alert_lifecycle(self) -> None:
        event = make_event()
        alert = make_alert(event, status=AlertStatus.ACKNOWLEDGED)
        self.mock_svc.update_alert = AsyncMock(return_value=alert)

        client = TestClient(app)
        response = client.patch(
            f"/api/v1/alerts/{alert.id}",
            json={"status": "ACKNOWLEDGED"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ACKNOWLEDGED"

    def test_patch_alert_invalid_transition_returns_422(self) -> None:
        alert_id = uuid.uuid4()
        self.mock_svc.update_alert = AsyncMock(
            side_effect=HTTPException(
                status_code=422,
                detail="Invalid lifecycle transition from RESOLVED to NEW",
            )
        )

        client = TestClient(app)
        response = client.patch(
            f"/api/v1/alerts/{alert_id}",
            json={"status": "NEW"},
        )
        assert response.status_code == 422
        assert "Invalid lifecycle transition" in response.json()["detail"]
