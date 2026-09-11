"""Internal schema representations for raw AI detections, tracked objects, and validated observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class BoundingBox:
    """Bounding box pixel coordinates (x1, y1, x2, y2)."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    def iou(self, other: BoundingBox) -> float:
        """Calculate Intersection over Union (IoU) with another bounding box."""
        inter_x1 = max(self.x1, other.x1)
        inter_y1 = max(self.y1, other.y1)
        inter_x2 = min(self.x2, other.x2)
        inter_y2 = min(self.y2, other.y2)

        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        if inter_area <= 0.0:
            return 0.0

        union_area = self.area + other.area - inter_area
        if union_area <= 0.0:
            return 0.0

        return float(inter_area / union_area)

    def to_dict(self) -> dict[str, float]:
        return {
            "x1": round(float(self.x1), 2),
            "y1": round(float(self.y1), 2),
            "x2": round(float(self.x2), 2),
            "y2": round(float(self.y2), 2),
        }


@dataclass
class Detection:
    """
    Internal representation of an individual object detection observation.

    Strictly decoupled from backend database models and avoids fabricating GPS coordinates.
    """

    class_id: int
    class_name: str
    confidence: float
    bounding_box: BoundingBox
    frame_number: int
    captured_at: datetime
    track_id: int | None = None
    bus_id: str | None = None
    camera_id: str | None = None
    stream_id: str | None = None
    raw_frame_number: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert detection to clean JSON-serializable dictionary."""
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(float(self.confidence), 4),
            "bounding_box": self.bounding_box.to_dict(),
            "track_id": self.track_id,
            "frame_number": self.frame_number,
            "raw_frame_number": self.raw_frame_number,
            "captured_at": self.captured_at.isoformat(),
            "bus_id": self.bus_id,
            "camera_id": self.camera_id,
            "stream_id": self.stream_id,
            "extra": self.extra,
        }


@dataclass
class TrackedDetection:
    """
    Representation of an object detection maintaining a persistent track_id across consecutive frames.
    """

    class_id: int
    class_name: str
    confidence: float
    bounding_box: BoundingBox
    track_id: int
    frame_number: int
    raw_frame_number: int
    captured_at: datetime
    bus_id: str | None = None
    camera_id: str | None = None
    stream_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert tracked detection to clean JSON-serializable dictionary."""
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(float(self.confidence), 4),
            "bounding_box": self.bounding_box.to_dict(),
            "track_id": self.track_id,
            "frame_number": self.frame_number,
            "raw_frame_number": self.raw_frame_number,
            "captured_at": self.captured_at.isoformat(),
            "bus_id": self.bus_id,
            "camera_id": self.camera_id,
            "stream_id": self.stream_id,
            "extra": self.extra,
        }


@dataclass
class ValidatedDetection:
    """
    Representation of a detection that has satisfied multi-frame temporal validation criteria.
    """

    tracked_detection: TrackedDetection
    track_id: int
    class_id: int
    class_name: str
    confidence: float
    bounding_box: BoundingBox
    frame_number: int
    raw_frame_number: int
    captured_at: datetime
    first_seen_frame: int
    last_seen_frame: int
    observation_count: int
    max_confidence: float
    average_confidence: float
    validated: bool = True
    last_seen_timestamp: datetime | None = None
    bus_id: str | None = None
    camera_id: str | None = None
    stream_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert validated detection to clean JSON-serializable dictionary."""
        return {
            "track_id": self.track_id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(float(self.confidence), 4),
            "bounding_box": self.bounding_box.to_dict(),
            "frame_number": self.frame_number,
            "raw_frame_number": self.raw_frame_number,
            "captured_at": self.captured_at.isoformat(),
            "first_seen_frame": self.first_seen_frame,
            "last_seen_frame": self.last_seen_frame,
            "observation_count": self.observation_count,
            "max_confidence": round(float(self.max_confidence), 4),
            "average_confidence": round(float(self.average_confidence), 4),
            "validated": self.validated,
            "last_seen_timestamp": (
                self.last_seen_timestamp.isoformat() if self.last_seen_timestamp else None
            ),
            "bus_id": self.bus_id,
            "camera_id": self.camera_id,
            "stream_id": self.stream_id,
            "extra": self.extra,
        }
