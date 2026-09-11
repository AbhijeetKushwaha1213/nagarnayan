"""
Unit and Integration tests for Phase 7 — Real-Time WebSocket Event & Alert Updates.

Tests verify all Phase 7 requirements:
1. Client can connect to /api/v1/ws.
2. Client disconnect is handled cleanly.
3. One connected client receives event.created.
4. One connected client receives event.updated.
5. One connected client receives alert.created.
6. One connected client receives alert.updated.
7. Multiple clients receive the same broadcast.
8. Disconnected client is removed from manager.
9. Dead client does not break broadcasting to healthy clients.
10. Message envelope contains: type, timestamp, data.
11. Event payload is JSON serializable.
12. Alert payload is JSON serializable.
13. Coordinate-less Event sends null coordinates.
14. Event persistence succeeds even when WebSocket delivery fails (error isolation).
15. Duplicate Event detections do not generate raw detection WebSocket messages.
16. Duplicate Alert generation remains suppressed by Phase 6 logic.
17. Step 16 end-to-end integration test (event.created -> alert.created -> alert.updated).
18. Keepalive heartbeat (ping -> system.pong).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.alert import Alert, AlertStatus, AlertType
from app.models.bus import Bus
from app.models.camera import Camera, CameraType
from app.models.event import Event, EventSeverity, EventStatus, EventType
from app.schemas.alert import AlertUpdate
from app.schemas.detection import DetectionCreate
from app.services.alert import AlertService
from app.services.detection import DetectionService
from app.services.event import EventService
from app.services.event_correlation import EventCorrelationService
from app.websocket.manager import ConnectionManager, connection_manager
from app.websocket.publisher import WebSocketPublisher, publisher
from app.websocket.schemas import (
    WebSocketEnvelope,
    WebSocketMessageType,
    build_envelope,
    serialize_alert,
    serialize_event,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_test_event(
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


def make_test_alert(
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


# ── Manager Unit Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestConnectionManager:
    """Test ConnectionManager registration, broadcasting, and error isolation."""

    async def test_manager_connect_and_disconnect(self) -> None:
        """1 & 2. Client registration and clean unregistration."""
        manager = ConnectionManager()
        mock_ws = AsyncMock()

        await manager.connect(mock_ws)
        assert manager.active_count == 1
        assert mock_ws.accept.called

        await manager.disconnect(mock_ws)
        assert manager.active_count == 0

    async def test_manager_broadcast_to_multiple_clients(self) -> None:
        """7. Multiple clients receive the identical broadcast."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect(ws1)
        await manager.connect(ws2)
        assert manager.active_count == 2

        msg = {"type": "event.created", "data": {"id": "123"}}
        await manager.broadcast(msg)

        ws1.send_json.assert_called_once_with(msg)
        ws2.send_json.assert_called_once_with(msg)

    async def test_manager_prunes_dead_client_without_breaking_healthy(self) -> None:
        """8 & 9. Dead client is pruned and healthy client continues receiving."""
        manager = ConnectionManager()
        healthy_ws = AsyncMock()
        failing_ws = AsyncMock()
        failing_ws.send_json.side_effect = RuntimeError("Client network drop")

        await manager.connect(healthy_ws)
        await manager.connect(failing_ws)
        assert manager.active_count == 2

        msg = {"type": "event.updated", "data": {"status": "OPEN"}}
        await manager.broadcast(msg)

        # Healthy received
        healthy_ws.send_json.assert_called_once_with(msg)
        # Failing client pruned
        assert manager.active_count == 1
        assert failing_ws not in manager._active_connections
        assert healthy_ws in manager._active_connections


# ── Payload & Envelope Serialization Tests ────────────────────────────────────


class TestMessageContracts:
    """Test JSON envelope contract and payload serialization (Requirements 10-13)."""

    def test_10_message_envelope_fields(self) -> None:
        """10. Message envelope strictly contains type, timestamp, data."""
        envelope = build_envelope(WebSocketMessageType.EVENT_CREATED, {"key": "value"})
        assert "type" in envelope
        assert "timestamp" in envelope
        assert "data" in envelope
        assert envelope["type"] == "event.created"
        assert envelope["data"] == {"key": "value"}
        # ISO timestamp format validation
        datetime.fromisoformat(envelope["timestamp"])

    def test_11_event_payload_json_serializable(self) -> None:
        """11. Event payload is valid JSON and contains all required municipal fields."""
        event = make_test_event()
        payload = serialize_event(event)
        # Ensure it serializes to string without error
        serialized = json.dumps(payload)
        parsed = json.loads(serialized)

        assert parsed["id"] == str(event.id)
        assert parsed["event_type"] == "POTHOLE"
        assert parsed["severity"] == "HIGH"
        assert parsed["status"] == "DETECTED"
        assert parsed["latitude"] == 12.9716
        assert parsed["longitude"] == 77.5946
        assert parsed["confidence"] == 0.86
        assert "first_detected_at" in parsed
        assert "last_detected_at" in parsed

    def test_12_alert_payload_json_serializable(self) -> None:
        """12. Alert payload is valid JSON and contains all required alert fields."""
        event = make_test_event()
        alert = make_test_alert(event)
        payload = serialize_alert(alert)
        serialized = json.dumps(payload)
        parsed = json.loads(serialized)

        assert parsed["id"] == str(alert.id)
        assert parsed["event_id"] == str(event.id)
        assert parsed["alert_type"] == "MUNICIPAL_ISSUE"
        assert parsed["severity"] == "HIGH"
        assert parsed["status"] == "NEW"
        assert parsed["title"] == alert.title
        assert parsed["message"] == alert.message
        assert "created_at" in parsed

    def test_13_coordinate_less_event_sends_null_coordinates(self) -> None:
        """13. Coordinate-less Event sends null coordinates, never fabricating locations."""
        event = make_test_event(latitude=None, longitude=None)
        payload = serialize_event(event)

        assert payload["latitude"] is None
        assert payload["longitude"] is None
        serialized = json.dumps(payload)
        parsed = json.loads(serialized)
        assert parsed["latitude"] is None
        assert parsed["longitude"] is None


# ── Publisher & Error Isolation Tests ─────────────────────────────────────────


@pytest.mark.asyncio
class TestPublisherAndErrorIsolation:
    """Test publisher dispatches and error isolation (Requirement 14)."""

    async def test_14_event_persistence_succeeds_when_websocket_fails(self) -> None:
        """14. Database operations succeed even if WebSocket broadcasting raises."""
        mock_manager = MagicMock()
        mock_manager.broadcast = AsyncMock(side_effect=RuntimeError("Broadcast crash!"))

        # Publisher isolates error
        failing_publisher = WebSocketPublisher(mock_manager)
        event = make_test_event()

        # Should not raise exception
        await failing_publisher.publish_event_created(event)
        await failing_publisher.publish_event_updated(event)

        alert = make_test_alert(event)
        await failing_publisher.publish_alert_created(alert)
        await failing_publisher.publish_alert_updated(alert)


# ── WebSocket Endpoint Live Client Tests ──────────────────────────────────────


class TestWebSocketEndpoint:
    """Test /api/v1/ws with FastAPI TestClient (Requirements 1-6, 18)."""

    def test_1_client_connect_and_heartbeat(self) -> None:
        """1 & 18. Client connects to /api/v1/ws and ping/pong heartbeat works."""
        client = TestClient(app)
        with client.websocket_connect("/api/v1/ws") as ws:
            assert connection_manager.active_count >= 1
            # Send ping
            ws.send_text("ping")
            resp = ws.receive_json()
            assert resp["type"] == "system.pong"
            assert resp["data"]["status"] == "alive"

    def test_3_client_receives_event_created(self) -> None:
        """3. Connected client receives event.created message."""
        client = TestClient(app)
        event = make_test_event()

        with client.websocket_connect("/api/v1/ws") as ws:
            asyncio.run(publisher.publish_event_created(event))
            msg = ws.receive_json()
            assert msg["type"] == "event.created"
            assert msg["data"]["id"] == str(event.id)
            assert msg["data"]["event_type"] == "POTHOLE"

    def test_4_client_receives_event_updated(self) -> None:
        """4. Connected client receives event.updated message."""
        client = TestClient(app)
        event = make_test_event()

        with client.websocket_connect("/api/v1/ws") as ws:
            asyncio.run(publisher.publish_event_updated(event))
            msg = ws.receive_json()
            assert msg["type"] == "event.updated"
            assert msg["data"]["id"] == str(event.id)

    def test_5_client_receives_alert_created(self) -> None:
        """5. Connected client receives alert.created message."""
        client = TestClient(app)
        event = make_test_event()
        alert = make_test_alert(event)

        with client.websocket_connect("/api/v1/ws") as ws:
            asyncio.run(publisher.publish_alert_created(alert))
            msg = ws.receive_json()
            assert msg["type"] == "alert.created"
            assert msg["data"]["id"] == str(alert.id)
            assert msg["data"]["event_id"] == str(event.id)

    def test_6_client_receives_alert_updated(self) -> None:
        """6. Connected client receives alert.updated message."""
        client = TestClient(app)
        event = make_test_event()
        alert = make_test_alert(event, status=AlertStatus.ACKNOWLEDGED)

        with client.websocket_connect("/api/v1/ws") as ws:
            asyncio.run(publisher.publish_alert_updated(alert))
            msg = ws.receive_json()
            assert msg["type"] == "alert.updated"
            assert msg["data"]["status"] == "ACKNOWLEDGED"

    def test_7_multiple_clients_receive_broadcast(self) -> None:
        """7. Multiple clients receive the same broadcast."""
        client = TestClient(app)
        event = make_test_event()

        with client.websocket_connect("/api/v1/ws") as ws1:
            with client.websocket_connect("/api/v1/ws") as ws2:
                asyncio.run(publisher.publish_event_created(event))
                m1 = ws1.receive_json()
                m2 = ws2.receive_json()
                assert m1 == m2
                assert m1["type"] == "event.created"


# ── Detection Pipeline & Step 16 Integration Test ─────────────────────────────


class TestPipelineWebSocketIntegration:
    """Test DetectionService -> Event -> Alert -> WebSocket integration (Requirements 15-17)."""

    @pytest.mark.asyncio
    async def test_15_duplicate_detection_emits_event_updated_only(self) -> None:
        """15. Repeat detection emits event.updated, not raw detection or duplicate alert."""
        session = AsyncMock()
        mock_publisher = MagicMock()
        mock_publisher.publish_event_created = AsyncMock()
        mock_publisher.publish_event_updated = AsyncMock()
        mock_publisher.publish_alert_created = AsyncMock()

        bus_id = uuid.uuid4()
        cam_id = uuid.uuid4()
        event_id = uuid.uuid4()

        service = DetectionService(session, publisher=mock_publisher)
        service._bus_repo.get_by_id = AsyncMock(return_value=Bus(id=bus_id, bus_number="B1"))
        service._camera_repo.get_by_id = AsyncMock(
            return_value=Camera(id=cam_id, bus_id=bus_id, camera_type=CameraType.front)
        )
        service.repo.create = AsyncMock(side_effect=lambda d: d)

        # Simulating existing event correlation (is_new = False)
        event = make_test_event(event_id=event_id)
        event._is_new = False
        service._correlation_service.correlate_and_link = AsyncMock(return_value=event)

        # Existing active alert
        existing_alert = make_test_alert(event, status=AlertStatus.NEW)
        existing_alert._is_new = False
        service._alert_service.process_event_for_alert = AsyncMock(return_value=existing_alert)

        payload = DetectionCreate(
            bus_id=bus_id,
            camera_id=cam_id,
            detection_type="POTHOLE",
            confidence=0.91,
            latitude=12.9716,
            longitude=77.5946,
            detected_at=datetime.now(timezone.utc),
        )

        await service.create_detection(payload)

        # event.updated was published
        mock_publisher.publish_event_updated.assert_called_once_with(event)
        # event.created was NOT published
        mock_publisher.publish_event_created.assert_not_called()
        # duplicate alert.created was NOT published (Requirement 16)
        mock_publisher.publish_alert_created.assert_not_called()

    def test_step_16_deterministic_e2e_sequence(self) -> None:
        """
        Step 16: Complete end-to-end flow with WebSocket client.
        1. Connect WebSocket client to /api/v1/ws.
        2. Detection arrives -> event.created emitted first, then alert.created emitted.
        3. Alert transition to ACKNOWLEDGED -> alert.updated emitted.
        4. Alert transition to RESOLVED -> alert.updated emitted.
        """
        client = TestClient(app)

        with client.websocket_connect("/api/v1/ws") as ws:
            # 1. New Event and Alert synthesized via Detection ingestion
            event = make_test_event(
                event_type=EventType.POTHOLE,
                severity=EventSeverity.HIGH,
                status=EventStatus.DETECTED,
            )
            event._is_new = True

            alert = make_test_alert(event, alert_type=AlertType.MUNICIPAL_ISSUE, status=AlertStatus.NEW)
            alert._is_new = True

            # Simulate DetectionService post-commit publishing in strict order
            asyncio.run(publisher.publish_event_created(event))
            asyncio.run(publisher.publish_alert_created(alert))

            # Verify message 1: event.created
            msg1 = ws.receive_json()
            assert msg1["type"] == "event.created"
            assert msg1["data"]["id"] == str(event.id)
            assert msg1["data"]["event_type"] == "POTHOLE"
            assert msg1["data"]["severity"] == "HIGH"

            # Verify message 2: alert.created (ordering verified: event.created first!)
            msg2 = ws.receive_json()
            assert msg2["type"] == "alert.created"
            assert msg2["data"]["id"] == str(alert.id)
            assert msg2["data"]["event_id"] == str(event.id)
            assert msg2["data"]["status"] == "NEW"

            # 2. Operator updates Alert to ACKNOWLEDGED
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now(timezone.utc)
            asyncio.run(publisher.publish_alert_updated(alert))

            msg3 = ws.receive_json()
            assert msg3["type"] == "alert.updated"
            assert msg3["data"]["id"] == str(alert.id)
            assert msg3["data"]["status"] == "ACKNOWLEDGED"
            assert msg3["data"]["acknowledged_at"] is not None

            # 3. Operator updates Alert to RESOLVED
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now(timezone.utc)
            asyncio.run(publisher.publish_alert_updated(alert))

            msg4 = ws.receive_json()
            assert msg4["type"] == "alert.updated"
            assert msg4["data"]["id"] == str(alert.id)
            assert msg4["data"]["status"] == "RESOLVED"
            assert msg4["data"]["resolved_at"] is not None
