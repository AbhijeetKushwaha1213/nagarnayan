"""Unit tests for Phase 9 Demo Telemetry Provider and payload attachment."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.backend.detection_sender import DetectionSender
from app.core.config import settings
from app.detection.schemas import BoundingBox, TrackedDetection, ValidatedDetection
from app.telemetry.demo_telemetry import DemoTelemetryProvider


def test_demo_telemetry_disabled_by_default() -> None:
    """When DEMO_TELEMETRY_ENABLED is false, zero GPS is fabricated."""
    original = settings.DEMO_TELEMETRY_ENABLED
    try:
        settings.DEMO_TELEMETRY_ENABLED = False
        lat, lon, meta = DemoTelemetryProvider.resolve_telemetry()
        assert lat is None
        assert lon is None
        assert meta == {}
    finally:
        settings.DEMO_TELEMETRY_ENABLED = original


def test_demo_telemetry_enabled_resolves_defined_coordinates() -> None:
    """When DEMO_TELEMETRY_ENABLED is true, explicit demo coordinates and metadata are returned."""
    original = settings.DEMO_TELEMETRY_ENABLED
    try:
        settings.DEMO_TELEMETRY_ENABLED = True
        lat, lon, meta = DemoTelemetryProvider.resolve_telemetry()
        assert lat == settings.DEMO_TELEMETRY_LATITUDE
        assert lon == settings.DEMO_TELEMETRY_LONGITUDE
        assert meta["telemetry_source"] == "DEMO_SIMULATED"
        assert meta["is_demo_telemetry"] is True
        assert meta["demo_route_id"] == settings.DEMO_TELEMETRY_ROUTE_ID
    finally:
        settings.DEMO_TELEMETRY_ENABLED = original


def test_detection_sender_attaches_demo_telemetry_when_enabled() -> None:
    """DetectionSender.build_payload includes demo coordinates and provenance when enabled."""
    original = settings.DEMO_TELEMETRY_ENABLED
    try:
        settings.DEMO_TELEMETRY_ENABLED = True
        sender = DetectionSender(start_worker=False)

        bbox = BoundingBox(x1=10.0, y1=10.0, x2=50.0, y2=50.0)
        now = datetime(2026, 9, 11, 12, 0, 0, tzinfo=timezone.utc)
        td = TrackedDetection(
            class_id=2,
            class_name="car",
            confidence=0.88,
            bounding_box=bbox,
            track_id=42,
            frame_number=5,
            raw_frame_number=150,
            captured_at=now,
            bus_id="00000000-0000-0000-0000-000000000001",
            camera_id="00000000-0000-0000-0000-000000000001",
            stream_id="00000000-0000-0000-0000-000000000001",
        )

        detection = ValidatedDetection(
            tracked_detection=td,
            track_id=42,
            class_name="car",
            class_id=2,
            confidence=0.88,
            bounding_box=bbox,
            first_seen_frame=1,
            last_seen_frame=5,
            observation_count=5,
            max_confidence=0.92,
            average_confidence=0.88,
            captured_at=now,
            frame_number=5,
            raw_frame_number=150,
            validated=True,
            bus_id="00000000-0000-0000-0000-000000000001",
            camera_id="00000000-0000-0000-0000-000000000001",
            stream_id="00000000-0000-0000-0000-000000000001",
        )

        payload = sender.build_payload(detection)
        assert payload is not None
        assert payload.latitude == settings.DEMO_TELEMETRY_LATITUDE
        assert payload.longitude == settings.DEMO_TELEMETRY_LONGITUDE
        assert payload.metadata["telemetry_source"] == "DEMO_SIMULATED"
        assert payload.metadata["is_demo_telemetry"] is True
    finally:
        settings.DEMO_TELEMETRY_ENABLED = original
