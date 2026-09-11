"""Mapping utilities between YOLO class labels, backend detection types, and deterministic frame references."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Strict mapping: Only semantic matches are accepted.
# Generic COCO objects are NEVER misclassified as municipal infrastructure defects.
YOLO_CLASS_TO_BACKEND_DETECTION_TYPE: dict[str, str] = {
    # COCO Vehicles -> VEHICLE
    "car": "VEHICLE",
    "truck": "VEHICLE",
    "bus": "VEHICLE",
    "motorcycle": "VEHICLE",
    "bicycle": "VEHICLE",
    "vehicle": "VEHICLE",

    # COCO Pedestrians -> PEDESTRIAN
    "person": "PEDESTRIAN",
    "pedestrian": "PEDESTRIAN",

    # Municipal infrastructure defect classes (reserved for specialized models)
    "pothole": "POTHOLE",
    "damaged_road": "DAMAGED_ROAD",
    "road_damage": "DAMAGED_ROAD",
    "waterlogging": "WATERLOGGING",
    "missing_divider": "MISSING_DIVIDER",
    "missing_zebra_crossing": "MISSING_ZEBRA_CROSSING",
    "missing_signboard": "MISSING_SIGNBOARD",
    "traffic_congestion": "TRAFFIC_CONGESTION",
}


def map_class_to_detection_type(class_name: str) -> str | None:
    """
    Map a YOLO/COCO class name to an accepted backend detection_type.

    Returns:
        Mapped string (e.g. 'VEHICLE', 'PEDESTRIAN') or None if unmapped.
        Unmapped classes (e.g. 'kite', 'sports ball', 'chair') are skipped.
    """
    normalized = str(class_name).strip().lower().replace(" ", "_")
    detection_type = YOLO_CLASS_TO_BACKEND_DETECTION_TYPE.get(normalized)
    if detection_type is None:
        logger.debug(
            "YOLO class %r has no valid backend detection type mapping. Skipping.",
            class_name,
        )
        return None
    return detection_type


def build_frame_reference(
    stream_id: str | None,
    camera_id: str,
    raw_frame_number: int,
    track_id: int,
    detection_type: str,
) -> str:
    """
    Build a deterministic, stable frame reference for backend idempotency deduplication.

    Format:
        <stream_id or camera_id>:<raw_frame_number>:<track_id>:<detection_type>

    Guarantees:
      - Deterministic across retries of the exact same observation.
      - Stable representation allowing backend idempotency filter to match.
      - Zero random UUIDs used for frame reference.
    """
    source_id = str(stream_id).strip() if stream_id else str(camera_id).strip()
    return f"{source_id}:{int(raw_frame_number)}:{int(track_id)}:{str(detection_type).strip().upper()}"
