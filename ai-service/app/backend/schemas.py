"""Data transfer schemas for the AI Video Intelligence Service to FastAPI Backend contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class BackendDetectionPayload:
    """
    Payload strictly adhering to the FastAPI Backend POST /api/v1/detections (DetectionCreate) schema.

    Rules:
      - Never fabricate GPS coordinates: latitude and longitude are None when unavailable.
      - frame_reference must be deterministic for backend idempotency deduplication.
      - metadata encapsulates physical detection attributes (bounding box, track ID, observations).
    """

    bus_id: str
    camera_id: str
    detection_type: str
    confidence: float
    detected_at: str
    stream_id: str | None = None
    frame_reference: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    latitude: float | None = None
    longitude: float | None = None
    event_id: str | None = None

    def __post_init__(self) -> None:
        # Normalize and validate confidence bounds
        self.confidence = max(0.0, min(1.0, round(float(self.confidence), 4)))

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary matching FastAPI DetectionCreate contract."""
        payload: dict[str, Any] = {
            "bus_id": self.bus_id,
            "camera_id": self.camera_id,
            "stream_id": self.stream_id,
            "detection_type": self.detection_type,
            "confidence": self.confidence,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "detected_at": self.detected_at,
            "frame_reference": self.frame_reference,
            "metadata": self.metadata,
        }
        if self.event_id is not None:
            payload["event_id"] = self.event_id
        return payload
