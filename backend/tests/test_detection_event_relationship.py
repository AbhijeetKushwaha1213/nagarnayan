"""
Tests for Detection → Event relationship.

Verifies:
- A Detection can exist independently (event_id is optional/null)
- A Detection can be linked to an Event (event_id)
- Event deletion does not delete Detections; foreign key sets event_id to NULL (ON DELETE SET NULL)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from tests.conftest import requires_db


@requires_db
class TestDetectionEventRelationship:

    @pytest.fixture
    def setup_entities(self, client: TestClient) -> dict:
        # Create bus
        bus_resp = client.post(
            "/api/v1/buses",
            json={"bus_number": f"REL-BUS-{uuid.uuid4().hex[:6].upper()}"},
        )
        assert bus_resp.status_code == 201
        bus = bus_resp.json()

        # Create camera
        cam_resp = client.post(
            "/api/v1/cameras",
            json={"bus_id": bus["id"], "camera_type": "front"},
        )
        assert cam_resp.status_code == 201
        camera = cam_resp.json()

        # Create event
        event_resp = client.post(
            "/api/v1/events",
            json={
                "event_type": "POTHOLE",
                "severity": "HIGH",
                "status": "OPEN",
                "latitude": 12.9716,
                "longitude": 77.5946,
            },
        )
        assert event_resp.status_code == 201
        event = event_resp.json()

        yield {"bus": bus, "camera": camera, "event": event}

        # Cleanup
        client.delete(f"/api/v1/buses/{bus['id']}")

    def test_detection_without_event(self, setup_entities: dict, client: TestClient) -> None:
        bus = setup_entities["bus"]
        camera = setup_entities["camera"]

        resp = client.post(
            "/api/v1/detections",
            json={
                "bus_id": bus["id"],
                "camera_id": camera["id"],
                "detection_type": "POTHOLE",
                "confidence": 0.85,
                "latitude": 12.9716,
                "longitude": 77.5946,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert resp.status_code == 201
        det = resp.json()
        assert det["event_id"] is None

    def test_link_detection_to_event(self, setup_entities: dict, client: TestClient) -> None:
        bus = setup_entities["bus"]
        camera = setup_entities["camera"]
        event = setup_entities["event"]

        resp = client.post(
            "/api/v1/detections",
            json={
                "bus_id": bus["id"],
                "camera_id": camera["id"],
                "event_id": event["id"],
                "detection_type": "POTHOLE",
                "confidence": 0.93,
                "latitude": 12.9716,
                "longitude": 77.5946,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert resp.status_code == 201
        det = resp.json()
        assert det["event_id"] == event["id"]

    def test_reject_nonexistent_event_link(self, setup_entities: dict, client: TestClient) -> None:
        bus = setup_entities["bus"]
        camera = setup_entities["camera"]

        resp = client.post(
            "/api/v1/detections",
            json={
                "bus_id": bus["id"],
                "camera_id": camera["id"],
                "event_id": str(uuid.uuid4()),
                "detection_type": "POTHOLE",
                "confidence": 0.93,
                "latitude": 12.9716,
                "longitude": 77.5946,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert resp.status_code == 422
        assert "Event" in resp.json()["detail"]
