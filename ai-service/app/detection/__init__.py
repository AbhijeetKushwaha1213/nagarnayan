"""Detection and tracking package exposing schemas, YOLODetector, and ObjectTracker."""

from app.detection.detector import YOLODetector
from app.detection.schemas import BoundingBox, Detection, TrackedDetection, ValidatedDetection
from app.detection.tracker import ObjectTracker, Track

__all__ = [
    "BoundingBox",
    "Detection",
    "TrackedDetection",
    "ValidatedDetection",
    "YOLODetector",
    "Track",
    "ObjectTracker",
]
