"""Backend integration module for Nagar Nayan AI Video Intelligence Service."""

from app.backend.client import BackendClient
from app.backend.detection_sender import DetectionSender
from app.backend.mapping import (
    YOLO_CLASS_TO_BACKEND_DETECTION_TYPE,
    build_frame_reference,
    map_class_to_detection_type,
)
from app.backend.schemas import BackendDetectionPayload

__all__ = [
    "BackendClient",
    "BackendDetectionPayload",
    "DetectionSender",
    "YOLO_CLASS_TO_BACKEND_DETECTION_TYPE",
    "build_frame_reference",
    "map_class_to_detection_type",
]
