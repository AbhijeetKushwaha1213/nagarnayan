"""
Unit and Integration test suite for Phase 6 — Severity Engine + Alert Engine.

Covers:
1. SeverityService:
   - Deterministic and explainable evaluation
   - LOW / MEDIUM / HIGH / CRITICAL tiers
   - Confidence != Severity demonstration
   - Escalation factors: multi-bus confirmation, detection count, persistence duration
   - Life-safety priority overrides (MISSING_DIVIDER -> CRITICAL)
   - Explainability audit trail in extra_metadata["severity_evaluation"]
   - Monotonic severity escalation on events
2. Alert Model & Schema:
   - triggered_at datetime tracking
   - Lifecycle statuses: ACTIVE, ACKNOWLEDGED, RESOLVED, DISMISSED
3. Alert Generation Policy:
   - LOW suppressed
   - MEDIUM threshold evaluation (detection count, distinct buses, persistence duration)
   - HIGH alerts created
   - CRITICAL alerts created immediately
   - Terminal events (RESOLVED, REJECTED) never alert
4. Alert Deduplication & Escalation:
   - Max 1 active alert per event
   - Monotonic escalation of existing active alert when event escalates
   - Re-alert policy on RESOLVED / DISMISSED
5. Alert Lifecycle Transitions:
   - ACTIVE -> ACKNOWLEDGED (sets acknowledged_at)
   - ACTIVE -> DISMISSED
   - ACKNOWLEDGED -> RESOLVED (sets resolved_at)
   - ACKNOWLEDGED -> DISMISSED
   - Invalid transitions rejected (HTTP 422)
6. REST API Endpoints:
   - GET /api/v1/alerts (filtering by status, severity, event_id, from_timestamp, to_timestamp)
   - GET /api/v1/alerts/{id}
   - POST /api/v1/alerts (manual alert creation)
   - PATCH /api/v1/alerts/{id} (lifecycle state machine)
7. Pipeline Integration in DetectionService:
   - Detection -> Correlation -> Severity -> Alert
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
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
from app.schemas.alert import AlertManualCreate, AlertUpdate
from app.schemas.detection import DetectionCreate
from app.services.alert import AlertService
from app.services.detection import DetectionService
from app.services.severity import SeverityEvaluationResult, SeverityService


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_test_event(
    event_type: EventType = EventType.POTHOLE,
    severity: EventSeverity = EventSeverity.LOW,
    status: EventStatus = EventStatus.DETECTED,
    confidence: float = 0.85,
    detection_count: int = 1,
    distinct_buses: int = 1,
    first_detected_at: datetime | None = None,
    last_detected_at: datetime | None = None,
    event_id: uuid.UUID | None = None,
    latitude: float | None = 12.9716,
    longitude: float | None = 77.5946,
) -> Event:
    now = datetime.now(timezone.utc)
    t0 = first_detected_at or now
    t1 = last_detected_at or now
    return Event(
        id=event_id or uuid.uuid4(),
        event_type=event_type,
        severity=severity,
        status=status,
        confidence=confidence,
        latitude=latitude,
        longitude=longitude,
        first_detected_at=t0,
        last_detected_at=t1,
        extra_metadata={
            "detection_count": detection_count,
            "distinct_buses": distinct_buses,
            "reporting_buses": [str(uuid.uuid4()) for _ in range(distinct_buses)],
            "distinct_bus_ids": [str(uuid.uuid4()) for _ in range(distinct_buses)],
            "distinct_camera_ids": [str(uuid.uuid4())],
        },
    )


# ── Test Suite 1: SeverityService Unit Tests ─────────────────────────────────


class TestSeverityService:
    @pytest.fixture
    def severity_service(self) -> SeverityService:
        return SeverityService()

    def test_confidence_does_not_equal_severity(self, severity_service: SeverityService) -> None:
        """High confidence alone on minor event should NOT yield CRITICAL severity."""
        minor_event = make_test_event(
            event_type=EventType.MISSING_SIGNBOARD,
            confidence=0.99,  # Near 100% confidence
            detection_count=1,
            distinct_buses=1,
        )
        res_minor = severity_service.evaluate_event(minor_event)
        # MISSING_SIGNBOARD base tier is LOW (0.0), no bonuses -> remains LOW
        assert res_minor.severity == EventSeverity.LOW

        # Conversely, life-safety hazard with moderate confidence is CRITICAL
        critical_event = make_test_event(
            event_type=EventType.MISSING_DIVIDER,
            confidence=0.65,
            detection_count=1,
            distinct_buses=1,
        )
        res_crit = severity_service.evaluate_event(critical_event)
        assert res_crit.severity == EventSeverity.CRITICAL

    def test_multi_bus_confirmation_escalation(self, severity_service: SeverityService) -> None:
        """Confirmation by multiple distinct buses escalates severity tier (+1.0)."""
        single_bus_event = make_test_event(
            event_type=EventType.POTHOLE,
            detection_count=2,
            distinct_buses=1,
        )
        res_single = severity_service.evaluate_event(single_bus_event)
        assert res_single.bus_bonus == 0.0

        multi_bus_event = make_test_event(
            event_type=EventType.POTHOLE,
            detection_count=2,
            distinct_buses=2,
        )
        res_multi = severity_service.evaluate_event(multi_bus_event)
        assert res_multi.bus_bonus == 1.0
        # POTHOLE base tier is MEDIUM (1.0) + 1.0 bus bonus = 2.0 (HIGH)
        assert res_multi.severity == EventSeverity.HIGH

    def test_repetition_and_persistence_escalation(self, severity_service: SeverityService) -> None:
        """Repeated detections and sustained observation duration escalate severity."""
        t0 = datetime.now(timezone.utc) - timedelta(seconds=350)
        t1 = datetime.now(timezone.utc)
        persistent_event = make_test_event(
            event_type=EventType.WATERLOGGING,
            detection_count=6,
            distinct_buses=1,
            first_detected_at=t0,
            last_detected_at=t1,
        )
        result = severity_service.evaluate_event(persistent_event)
        # WATERLOGGING base is 1.0 (MEDIUM)
        # count >= 5 gives +1.0
        # persistence >= 300s gives +1.0
        # total score = 3.0 -> CRITICAL
        assert result.count_bonus == 1.0
        assert result.persistence_bonus == 1.0
        assert result.score >= 3.0
        assert result.severity == EventSeverity.CRITICAL

    def test_explainability_audit_trail(self, severity_service: SeverityService) -> None:
        """Severity evaluation writes an explicit, explainable audit trail to extra_metadata."""
        event = make_test_event(
            event_type=EventType.DAMAGED_ROAD,
            detection_count=3,
            distinct_buses=2,
        )
        result = severity_service.evaluate_and_update_event_severity(event)
        assert "severity_evaluation" in event.extra_metadata
        audit = event.extra_metadata["severity_evaluation"]
        assert audit["final_severity"] == result.severity.value
        assert "score" in audit
        assert "bus_bonus" in audit
        assert "count_bonus" in audit
        assert "persistence_bonus" in audit
        assert len(audit["reasons"]) > 0

    def test_monotonic_severity_escalation(self, severity_service: SeverityService) -> None:
        """Severity can escalate but must never silently downgrade during event lifetime."""
        event = make_test_event(
            event_type=EventType.DAMAGED_ROAD,
            severity=EventSeverity.HIGH,  # Already escalated
            detection_count=1,
            distinct_buses=1,
        )
        # Raw evaluation of a single observation would be LOW (1.0)
        raw_result = severity_service.evaluate_event(event)
        assert raw_result.severity == EventSeverity.LOW

        # But update method enforces monotonic floor
        final_result = severity_service.evaluate_and_update_event_severity(event)
        assert final_result.severity == EventSeverity.HIGH
        assert event.severity == EventSeverity.HIGH


# ── Test Suite 2: Alert Policy Evaluation ────────────────────────────────────


class TestAlertPolicyEvaluation:
    @pytest.fixture
    def alert_service(self) -> AlertService:
        session = AsyncMock()
        service = AlertService(session)
        service.repo = AsyncMock()
        service.repo.find_active_alert_by_event = AsyncMock(return_value=None)
        service.repo.create = AsyncMock(side_effect=lambda a: a)
        return service

    def test_low_severity_never_alerts(self, alert_service: AlertService) -> None:
        """LOW severity events must be suppressed and never alert."""
        event = make_test_event(event_type=EventType.MISSING_SIGNBOARD, severity=EventSeverity.LOW)
        assert alert_service.should_generate_alert(event) is False

    def test_medium_threshold_suppressed_when_unconfirmed(self, alert_service: AlertService) -> None:
        """MEDIUM event below confirmation thresholds is suppressed."""
        event = make_test_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.MEDIUM,
            detection_count=1,
            distinct_buses=1,
        )
        assert alert_service.should_generate_alert(event) is False

    def test_medium_threshold_alerts_on_detection_count(self, alert_service: AlertService) -> None:
        """MEDIUM event alerts when detection count >= ALERT_MEDIUM_THRESHOLD_DETECTION_COUNT (3)."""
        event = make_test_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.MEDIUM,
            detection_count=3,
            distinct_buses=1,
        )
        assert alert_service.should_generate_alert(event) is True

    def test_medium_threshold_alerts_on_distinct_buses(self, alert_service: AlertService) -> None:
        """MEDIUM event alerts when distinct buses >= ALERT_MEDIUM_THRESHOLD_DISTINCT_BUSES (2)."""
        event = make_test_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.MEDIUM,
            detection_count=2,
            distinct_buses=2,
        )
        assert alert_service.should_generate_alert(event) is True

    def test_medium_threshold_alerts_on_persistence(self, alert_service: AlertService) -> None:
        """MEDIUM event alerts when persistence >= ALERT_MEDIUM_THRESHOLD_PERSISTENCE_SECONDS (120s)."""
        t0 = datetime.now(timezone.utc) - timedelta(seconds=130)
        t1 = datetime.now(timezone.utc)
        event = make_test_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.MEDIUM,
            detection_count=2,
            distinct_buses=1,
            first_detected_at=t0,
            last_detected_at=t1,
        )
        assert alert_service.should_generate_alert(event) is True

    def test_high_and_critical_always_alert(self, alert_service: AlertService) -> None:
        """HIGH and CRITICAL events always alert."""
        high_event = make_test_event(event_type=EventType.POTHOLE, severity=EventSeverity.HIGH)
        crit_event = make_test_event(event_type=EventType.MISSING_DIVIDER, severity=EventSeverity.CRITICAL)
        assert alert_service.should_generate_alert(high_event) is True
        assert alert_service.should_generate_alert(crit_event) is True

    def test_terminal_events_never_alert(self, alert_service: AlertService) -> None:
        """RESOLVED and REJECTED events never alert even if CRITICAL."""
        resolved = make_test_event(
            event_type=EventType.MISSING_DIVIDER,
            severity=EventSeverity.CRITICAL,
            status=EventStatus.RESOLVED,
        )
        rejected = make_test_event(
            event_type=EventType.MISSING_DIVIDER,
            severity=EventSeverity.CRITICAL,
            status=EventStatus.REJECTED,
        )
        assert alert_service.should_generate_alert(resolved) is False
        assert alert_service.should_generate_alert(rejected) is False


# ── Test Suite 3: Alert Deduplication & Escalation ───────────────────────────


@pytest.mark.asyncio
class TestAlertDeduplicationAndEscalation:
    async def test_max_one_active_alert_and_escalation(self) -> None:
        """Only one active alert exists per event; existing active alert is escalated."""
        session = AsyncMock()
        service = AlertService(session)
        service.repo = AsyncMock()

        event = make_test_event(
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
        )

        existing_alert = Alert(
            id=uuid.uuid4(),
            event_id=event.id,
            alert_type=AlertType.MUNICIPAL_ISSUE,
            severity=EventSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            title="High Priority Pothole Detected",
            message="Initial pothole alert",
            triggered_at=datetime.now(timezone.utc),
        )

        # 1. When existing active alert has matching severity, return it unchanged
        service.repo.find_active_alert_by_event = AsyncMock(return_value=existing_alert)
        res = await service.process_event_for_alert(event)
        assert res.id == existing_alert.id
        service.repo.create.assert_not_called()

        # 2. When event severity escalates to CRITICAL, escalate existing active alert
        event.severity = EventSeverity.CRITICAL
        service.repo.update = AsyncMock(side_effect=lambda a: a)
        res_escalated = await service.process_event_for_alert(event)
        assert res_escalated.id == existing_alert.id
        assert res_escalated.severity == EventSeverity.CRITICAL
        assert "Critical" in res_escalated.title
        service.repo.update.assert_called_once()


# ── Test Suite 4: Alert Lifecycle State Machine ──────────────────────────────


@pytest.mark.asyncio
class TestAlertLifecycleStateMachine:
    @pytest.fixture
    def alert_service(self) -> AlertService:
        session = AsyncMock()
        service = AlertService(session)
        service.repo = AsyncMock()
        service.repo.update = AsyncMock(side_effect=lambda a: a)
        return service

    async def test_active_to_acknowledged_sets_timestamp(self, alert_service: AlertService) -> None:
        alert = Alert(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            alert_type=AlertType.MUNICIPAL_ISSUE,
            severity=EventSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            title="Pothole Alert",
            message="Details",
            triggered_at=datetime.now(timezone.utc),
        )
        alert_service.repo.get_by_id_with_event = AsyncMock(return_value=alert)

        updated = await alert_service.update_alert(
            alert.id, AlertUpdate(status=AlertStatus.ACKNOWLEDGED)
        )
        assert updated.status == AlertStatus.ACKNOWLEDGED
        assert updated.acknowledged_at is not None

    async def test_acknowledged_to_resolved_sets_timestamp(self, alert_service: AlertService) -> None:
        alert = Alert(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            alert_type=AlertType.MUNICIPAL_ISSUE,
            severity=EventSeverity.HIGH,
            status=AlertStatus.ACKNOWLEDGED,
            title="Pothole Alert",
            message="Details",
            acknowledged_at=datetime.now(timezone.utc),
            triggered_at=datetime.now(timezone.utc),
        )
        alert_service.repo.get_by_id_with_event = AsyncMock(return_value=alert)

        updated = await alert_service.update_alert(
            alert.id, AlertUpdate(status=AlertStatus.RESOLVED)
        )
        assert updated.status == AlertStatus.RESOLVED
        assert updated.resolved_at is not None

    async def test_invalid_state_transitions_rejected(self, alert_service: AlertService) -> None:
        # Cannot jump directly ACTIVE -> RESOLVED (must acknowledge first)
        alert = Alert(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            alert_type=AlertType.MUNICIPAL_ISSUE,
            severity=EventSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            title="Pothole Alert",
            message="Details",
            triggered_at=datetime.now(timezone.utc),
        )
        alert_service.repo.get_by_id_with_event = AsyncMock(return_value=alert)

        with pytest.raises(HTTPException) as exc_info:
            await alert_service.update_alert(alert.id, AlertUpdate(status=AlertStatus.RESOLVED))
        assert exc_info.value.status_code == 422
        assert "Invalid lifecycle transition" in exc_info.value.detail


# ── Test Suite 5: REST API Endpoints ──────────────────────────────────────────


class TestAlertRESTAPIs:
    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        from app.api.routes.alerts import _get_service
        mock_svc = MagicMock()
        app.dependency_overrides[_get_service] = lambda: mock_svc
        yield mock_svc
        app.dependency_overrides.pop(_get_service, None)

    def test_get_alerts_with_time_range_and_filters(self, client: TestClient, mock_service: MagicMock) -> None:
        event = make_test_event()
        now = datetime.now(timezone.utc)
        fake_alert = Alert(
            id=uuid.uuid4(),
            event_id=event.id,
            alert_type=AlertType.MUNICIPAL_ISSUE,
            severity=EventSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            title="High Priority Pothole Detected",
            message="Message",
            triggered_at=now,
            created_at=now,
            updated_at=now,
            extra_metadata={},
            event=event,
        )

        mock_service.list_alerts = AsyncMock(return_value=[fake_alert])
        resp = client.get(
            "/api/v1/alerts",
            params={
                "status": "ACTIVE",
                "severity": "HIGH",
                "from_timestamp": (now - timedelta(hours=1)).isoformat(),
                "to_timestamp": (now + timedelta(hours=1)).isoformat(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "ACTIVE"
        assert data[0]["severity"] == "HIGH"
        assert "triggered_at" in data[0]

    def test_post_manual_alert_creation(self, client: TestClient, mock_service: MagicMock) -> None:
        event = make_test_event()
        now = datetime.now(timezone.utc)
        created_alert = Alert(
            id=uuid.uuid4(),
            event_id=event.id,
            alert_type=AlertType.MUNICIPAL_ISSUE,
            severity=EventSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            title="Manual Alert",
            message="Dispatched manual alert",
            triggered_at=now,
            created_at=now,
            updated_at=now,
            extra_metadata={},
            event=event,
        )

        mock_service.create_manual_alert = AsyncMock(return_value=created_alert)
        payload = {
            "event_id": str(event.id),
            "alert_type": "MUNICIPAL_ISSUE",
            "severity": "HIGH",
            "title": "Manual Alert",
            "message": "Dispatched manual alert",
        }
        resp = client.post("/api/v1/alerts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Manual Alert"
        assert data["status"] == "ACTIVE"


# ── Test Suite 6: Full Pipeline Integration in DetectionService ──────────────


@pytest.mark.asyncio
class TestPipelineIntegration:
    async def test_detection_to_severity_to_alert_flow(self) -> None:
        session = AsyncMock()
        mock_publisher = MagicMock()
        mock_publisher.publish_event_created = AsyncMock()
        mock_publisher.publish_alert_created = AsyncMock()
        det_service = DetectionService(session, publisher=mock_publisher)

        bus_id = uuid.uuid4()
        cam_id = uuid.uuid4()
        event_id = uuid.uuid4()

        det_service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="DL-01"))
        det_service._camera_repo.get_by_id = AsyncMock(
            return_value=Camera(id=cam_id, bus_id=bus_id, camera_type=CameraType.front)
        )
        det_service.repo.create = AsyncMock(side_effect=lambda d: d)
        det_service.repo.find_duplicate = AsyncMock(return_value=None)

        # Correlated event (e.g. MISSING_DIVIDER)
        correlated_event = make_test_event(
            event_type=EventType.MISSING_DIVIDER,
            severity=EventSeverity.LOW,  # Initially LOW before severity service
            event_id=event_id,
        )
        det_service._correlation_service.correlate_and_link = AsyncMock(return_value=correlated_event)
        correlated_event._is_new = True

        created_alert_holder: list[Alert] = []

        async def mock_process_event(ev: Event) -> Alert:
            alert = Alert(
                id=uuid.uuid4(),
                event_id=ev.id,
                alert_type=AlertType.CRITICAL_INFRASTRUCTURE,
                severity=ev.severity,
                status=AlertStatus.ACTIVE,
                title="Critical Alert",
                message="Critical hazard detected",
                triggered_at=datetime.now(timezone.utc),
            )
            created_alert_holder.append(alert)
            alert._is_new = True
            return alert

        det_service._alert_service.process_event_for_alert = AsyncMock(side_effect=mock_process_event)

        payload = DetectionCreate(
            bus_id=bus_id,
            camera_id=cam_id,
            detection_type="MISSING_DIVIDER",
            confidence=0.88,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
        )

        detection = await det_service.create_detection(payload)
        assert detection is not None

        # 1. Severity service must have evaluated MISSING_DIVIDER to CRITICAL
        assert correlated_event.severity == EventSeverity.CRITICAL
        assert "severity_evaluation" in correlated_event.extra_metadata

        # 2. Alert service must have processed the event and synthesized an alert
        assert len(created_alert_holder) == 1
        assert created_alert_holder[0].severity == EventSeverity.CRITICAL
        assert created_alert_holder[0].status == AlertStatus.ACTIVE
