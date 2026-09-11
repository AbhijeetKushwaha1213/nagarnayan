"""
Nagar Nayan — Explicit Demo Telemetry Provider.

Phase 9: Controlled Demo Data Strategy.
Maps simulated video streams to predefined geographic coordinates for demo environments ONLY.
This module is strictly isolated from YOLO object detection, tracking, and validation.

Guarantees:
  - Never mixes demo coordinates with production telemetry.
  - In production (DEMO_TELEMETRY_ENABLED=False), returns None, None (zero invented GPS).
  - In demo mode (DEMO_TELEMETRY_ENABLED=True), attaches predefined coordinates and stamps
    metadata with {"telemetry_source": "DEMO_SIMULATED", "is_demo_telemetry": True}.
  - Completely decoupled from detector and tracker logic.
"""

from __future__ import annotations

from typing import Any
from app.core.config import settings


class DemoTelemetryProvider:
    """Explicitly isolated telemetry resolver for demo and simulation feeds."""

    @staticmethod
    def resolve_telemetry(
        bus_id: str | None = None,
        camera_id: str | None = None,
        stream_id: str | None = None,
    ) -> tuple[float | None, float | None, dict[str, Any]]:
        """
        Resolve GPS coordinates and telemetry provenance metadata.

        Returns:
            (latitude, longitude, provenance_metadata)
        """
        if not settings.DEMO_TELEMETRY_ENABLED:
            return None, None, {}

        # Predefined demo coordinates (e.g. Connaught Place, New Delhi)
        demo_meta: dict[str, Any] = {
            "telemetry_source": "DEMO_SIMULATED",
            "is_demo_telemetry": True,
            "demo_route_id": settings.DEMO_TELEMETRY_ROUTE_ID,
            "demo_stream_mapping": "simulated_rtsp_bus_front",
        }
        return (
            float(settings.DEMO_TELEMETRY_LATITUDE),
            float(settings.DEMO_TELEMETRY_LONGITUDE),
            demo_meta,
        )
