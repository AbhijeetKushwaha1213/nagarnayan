"""Structured typed representations for raw, tracked, and validated detections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BoundingBox:
    """Bounding box pixel coordinates (x1, y1) to (x2, y2)."""

    x1: float
    y1: float
    x2: float
    y2: float

    def to_dict(self) -> dict[str, float]:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    def iou(self, other: BoundingBox) -> float:
        """Compute Intersection over Union (IoU) with another bounding box."""
        inter_x1 = max(self.x1, other.x1)
        inter_y1 = max(self.y1, other.y1)
        inter_x2 = min(self.x2, other.x2)
        inter_y2 = min(self.y2, other.y2)

        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        self_area = max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)
        other_area = max(0.0, other.x2 - other.x1) * max(0.0, other.y2 - other.y1)
        union_area = self_area + other_area - inter_area

        if union_area <= 0.0:
            return 0.0
        return inter_area / union_area


@dataclass(frozen=True)
class Detection:
    """A raw object detection produced directly by YOLO."""

    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    track_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox.to_dict(),
        }
        if self.track_id is not None:
            data["track_id"] = self.track_id
        return data


@dataclass(frozen=True)
class TrackedDetection:
    """An object detection assigned a persistent track ID across frames."""

    track_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    frame_id: int
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox.to_dict(),
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class ValidatedDetection:
    """A multi-frame validated urban observation passing confidence and persistence criteria."""

    track_id: int
    class_id: int
    class_name: str
    confidence: float
    average_confidence: float
    bbox: BoundingBox
    frame_id: int
    timestamp: float
    frames_seen: int
    first_seen_timestamp: float
    last_seen_timestamp: float
    validation_status: str = "validated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "average_confidence": round(self.average_confidence, 4),
            "bbox": self.bbox.to_dict(),
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "frames_seen": self.frames_seen,
            "first_seen_timestamp": self.first_seen_timestamp,
            "last_seen_timestamp": self.last_seen_timestamp,
            "validation_status": self.validation_status,
        }


@dataclass(frozen=True)
class FrameDetections:
    """Aggregated detection results for a single video frame."""

    frame_id: int
    timestamp: float
    detections: list[Detection]
    inference_time_ms: float
    model_name: str

    @property
    def count(self) -> int:
        return len(self.detections)

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "count": self.count,
            "detection_count": self.count,
            "inference_time_ms": round(self.inference_time_ms, 2),
            "model_name": self.model_name,
            "detections": [d.to_dict() for d in self.detections],
        }
