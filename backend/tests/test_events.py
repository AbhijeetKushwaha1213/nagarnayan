"""
Tests for Event API — /api/v1/events

Validates urban event creation, retrieval, updates, status transitions,
lifecycle field maintenance, and filtering.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from tests.conftest import requires_db
from app.core.database import get_db
from app.main import app


class TestEventValidation:
    """Tests that exercise Pydantic schema validation without needing a database."""

    @pytest.fixture(autouse=True)
    def override_get_db(self) -> None:
        async def dummy_db():
            yield None

        app.dependency_overrides[get_db] = dummy_db
        yield
        app.dependency_overrides.pop(get_db, None)

    def test_reject_invalid_event_type(self, client: TestClient) -> None:
        payload = {
            "event_type": "INVALID_TYPE",
            "severity": "HIGH",
            "status": "OPEN",
            "latitude": 12.9716,
            "longitude": 77.5946,
        }
        resp = client.post("/api/v1/events", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_severity(self, client: TestClient) -> None:
        payload = {
            "event_type": "POTHOLE",
            "severity": "EXTREME",  # not in enum
            "status": "OPEN",
            "latitude": 12.9716,
            "longitude": 77.5946,
        }
        resp = client.post("/api/v1/events", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_status(self, client: TestClient) -> None:
        payload = {
            "event_type": "POTHOLE",
            "severity": "HIGH",
            "status": "NONEXISTENT",  # not in enum
            "latitude": 12.9716,
            "longitude": 77.5946,
        }
        resp = client.post("/api/v1/events", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_latitude(self, client: TestClient) -> None:
        payload = {
            "event_type": "POTHOLE",
            "latitude": 100.0,
            "longitude": 77.5946,
        }
        resp = client.post("/api/v1/events", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_longitude(self, client: TestClient) -> None:
        payload = {
            "event_type": "POTHOLE",
            "latitude": 12.9716,
            "longitude": -200.0,
        }
        resp = client.post("/api/v1/events", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_confidence(self, client: TestClient) -> None:
        payload = {
            "event_type": "POTHOLE",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "confidence": 1.5,
        }
        resp = client.post("/api/v1/events", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_uuid(self, client: TestClient) -> None:
        resp = client.get("/api/v1/events/not-a-valid-uuid")
        assert resp.status_code == 422


@requires_db
class TestEventCRUD:
    """Full database lifecycle tests for urban events."""

    def test_create_valid_event(self, client: TestClient) -> None:
        payload = {
            "event_type": "POTHOLE",
            "severity": "HIGH",
            "status": "DETECTED",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "confidence": 0.95,
            "metadata": {"road_name": "MG Road", "lane": 2},
        }
        resp = client.post("/api/v1/events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["event_type"] == "POTHOLE"
        assert data["severity"] == "HIGH"
        assert data["status"] == "DETECTED"
        assert data["latitude"] == 12.9716
        assert data["longitude"] == 77.5946
        assert data["confidence"] == 0.95
        assert data["metadata"]["road_name"] == "MG Road"
        assert "first_detected_at" in data
        assert "last_detected_at" in data

    def test_retrieve_event(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/v1/events",
            json={
                "event_type": "DAMAGED_ROAD",
                "severity": "MEDIUM",
                "status": "OPEN",
                "latitude": 12.9750,
                "longitude": 77.5980,
            },
        )
        assert create_resp.status_code == 201
        event_id = create_resp.json()["id"]

        get_resp = client.get(f"/api/v1/events/{event_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == event_id
        assert get_resp.json()["event_type"] == "DAMAGED_ROAD"

    def test_retrieve_event_not_found(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/events/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_event(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/v1/events",
            json={
                "event_type": "WATERLOGGING",
                "severity": "LOW",
                "status": "OPEN",
                "latitude": 12.9716,
                "longitude": 77.5946,
            },
        )
        assert create_resp.status_code == 201
        event_id = create_resp.json()["id"]

        update_resp = client.patch(
            f"/api/v1/events/{event_id}",
            json={"severity": "CRITICAL", "status": "IN_PROGRESS"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["severity"] == "CRITICAL"
        assert update_resp.json()["status"] == "IN_PROGRESS"

    def test_validate_lifecycle_fields(self, client: TestClient) -> None:
        # Create detected event
        create_resp = client.post(
            "/api/v1/events",
            json={
                "event_type": "MISSING_SIGNBOARD",
                "severity": "MEDIUM",
                "status": "DETECTED",
                "latitude": 12.9716,
                "longitude": 77.5946,
            },
        )
        assert create_resp.status_code == 201
        event = create_resp.json()
        assert event["verified_at"] is None
        assert event["resolved_at"] is None

        # Transition to VERIFIED sets verified_at
        verify_resp = client.patch(
            f"/api/v1/events/{event['id']}",
            json={"status": "VERIFIED"},
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["verified_at"] is not None

        # Transition to RESOLVED sets resolved_at
        resolve_resp = client.patch(
            f"/api/v1/events/{event['id']}",
            json={"status": "RESOLVED"},
        )
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["resolved_at"] is not None

    def test_filter_by_type(self, client: TestClient) -> None:
        resp = client.get("/api/v1/events?event_type=POTHOLE")
        assert resp.status_code == 200
        for e in resp.json():
            assert e["event_type"] == "POTHOLE"

    def test_filter_by_severity(self, client: TestClient) -> None:
        resp = client.get("/api/v1/events?severity=HIGH")
        assert resp.status_code == 200
        for e in resp.json():
            assert e["severity"] == "HIGH"

    def test_filter_by_status(self, client: TestClient) -> None:
        resp = client.get("/api/v1/events?status=OPEN")
        assert resp.status_code == 200
        for e in resp.json():
            assert e["status"] == "OPEN"


class TestEventGeoJSON:
    """Tests for GET /api/v1/events/geojson endpoint."""

    @pytest.fixture(autouse=True)
    def override_get_db(self) -> None:
        async def dummy_db():
            yield None

        app.dependency_overrides[get_db] = dummy_db
        yield
        app.dependency_overrides.pop(get_db, None)

    def test_geojson_endpoint_structure(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import AsyncMock
        from app.models.event import Event, EventSeverity, EventStatus, EventType
        import app.api.routes.events as events_route

        now = datetime.now(timezone.utc)
        event_id = uuid.uuid4()
        fake_event = Event(
            id=event_id,
            event_type=EventType.POTHOLE,
            severity=EventSeverity.HIGH,
            status=EventStatus.DETECTED,
            latitude=12.9716,
            longitude=77.5946,
            confidence=0.95,
            first_detected_at=now,
            last_detected_at=now,
            extra_metadata={},
        )

        monkeypatch.setattr(
            events_route.EventService,
            "list_events",
            AsyncMock(return_value=[fake_event]),
        )

        resp = client.get("/api/v1/events/geojson")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1
        feature = data["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["geometry"]["coordinates"] == [77.5946, 12.9716]
        assert feature["properties"]["event_id"] == str(event_id)
        assert feature["properties"]["event_type"] == "POTHOLE"
        assert feature["properties"]["status"] == "DETECTED"
        assert feature["properties"]["severity"] == "HIGH"
        assert feature["properties"]["confidence"] == 0.95
        assert "detected_at" in feature["properties"]

    def test_geojson_endpoint_null_coordinates(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import AsyncMock
        from app.models.event import Event, EventSeverity, EventStatus, EventType
        import app.api.routes.events as events_route

        now = datetime.now(timezone.utc)
        event_id = uuid.uuid4()
        fake_event = Event(
            id=event_id,
            event_type=EventType.MISSING_SIGNBOARD,
            severity=EventSeverity.LOW,
            status=EventStatus.OPEN,
            latitude=None,
            longitude=None,
            confidence=0.8,
            first_detected_at=now,
            last_detected_at=now,
            extra_metadata={},
        )

        monkeypatch.setattr(
            events_route.EventService,
            "list_events",
            AsyncMock(return_value=[fake_event]),
        )

        resp = client.get("/api/v1/events/geojson")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1
        assert data["features"][0]["geometry"] is None

