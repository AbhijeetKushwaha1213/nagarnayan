"""HTTP client for ingesting validated detections into the FastAPI backend."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from typing import TYPE_CHECKING, Any

import httpx

from app.core.config import settings

if TYPE_CHECKING:
    from app.processing.detection_types import ValidatedDetection

logger = logging.getLogger(__name__)

# Mapping from AI/YOLO class names to standard backend municipal detection types
DEFAULT_DETECTION_TYPE_MAP: dict[str, str] = {
    "car": "VEHICLE",
    "truck": "VEHICLE",
    "bus": "VEHICLE",
    "motorcycle": "VEHICLE",
    "bicycle": "VEHICLE",
    "vehicle": "VEHICLE",
    "person": "PEDESTRIAN",
    "pedestrian": "PEDESTRIAN",
    "pothole": "POTHOLE",
    "garbage": "GARBAGE_DUMP",
    "garbage_dump": "GARBAGE_DUMP",
    "waterlogging": "WATERLOGGING",
    "damaged_road": "ROAD_DAMAGE",
    "road_damage": "ROAD_DAMAGE",
}


class DuplicateSendFilter:
    """In-memory duplicate-send filter tracking cooldown per (track_id, camera_id)."""

    def __init__(self, cooldown_seconds: float = 5.0) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._last_sent: dict[tuple[int, str], float] = {}

    def can_send(self, track_id: int, camera_id: str, current_timestamp: float) -> bool:
        """Check if sufficient time has passed since the last successful send."""
        key = (track_id, camera_id)
        last_time = self._last_sent.get(key)
        if last_time is None:
            return True
        return (current_timestamp - last_time) >= self.cooldown_seconds

    def record_sent(self, track_id: int, camera_id: str, current_timestamp: float) -> None:
        """Record successful transmission timestamp for the given track and camera."""
        self._last_sent[(track_id, camera_id)] = current_timestamp

    def reset(self) -> None:
        """Clear all in-memory send records."""
        self._last_sent.clear()


class BackendClient:
    """
    HTTP Client transmitting validated detections to FastAPI.

    Features:
      - Encapsulates bounded retries on transient errors (connection drops, 5xx).
      - Fails fast on 4xx validation errors without looping.
      - Enforces in-memory duplicate-send cooldowns per (track_id, camera_id).
      - Translates ValidatedDetection to backend DetectionCreate payload contract.
      - Tracks telemetry metrics (attempted, sent, failed, retries, latency).
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_prefix: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_delay_seconds: float | None = None,
        cooldown_seconds: float | None = None,
        type_mapping: dict[str, str] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = (base_url or settings.BACKEND_API_URL).rstrip("/")
        self.api_prefix = (api_prefix or settings.BACKEND_API_PREFIX).rstrip("/")
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.BACKEND_REQUEST_TIMEOUT_SECONDS
        )
        self.max_retries = (
            max_retries if max_retries is not None else settings.BACKEND_MAX_RETRIES
        )
        self.retry_delay_seconds = (
            retry_delay_seconds
            if retry_delay_seconds is not None
            else settings.BACKEND_RETRY_DELAY_SECONDS
        )
        self.type_mapping = type_mapping or DEFAULT_DETECTION_TYPE_MAP
        self.duplicate_filter = DuplicateSendFilter(
            cooldown_seconds=(
                cooldown_seconds
                if cooldown_seconds is not None
                else settings.DETECTION_SEND_COOLDOWN_SECONDS
            )
        )

        self._client = http_client or httpx.Client(timeout=self.timeout_seconds)
        self._endpoint = f"{self.base_url}{self.api_prefix}/detections"

        # Telemetry metrics
        self.detections_attempted: int = 0
        self.detections_sent: int = 0
        self.detections_failed: int = 0
        self.retry_count: int = 0
        self.last_successful_send: float | None = None
        self.total_request_latency_ms: float = 0.0

    @property
    def average_backend_request_latency_ms(self) -> float:
        """Average HTTP latency for completed requests."""
        total_finished = self.detections_sent + self.detections_failed
        if total_finished <= 0:
            return 0.0
        return round(self.total_request_latency_ms / total_finished, 2)

    def map_detection_type(self, class_name: str) -> str | None:
        """Resolve a YOLO/AI class name to the backend detection_type."""
        normalized = class_name.strip().lower()
        return self.type_mapping.get(normalized)

    def send_detection(
        self,
        detection: ValidatedDetection,
        camera_id: str | None = None,
        bus_id: str | None = None,
        frame_prefix: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> bool:
        """
        Transmit a validated detection to the FastAPI backend.

        Args:
            detection: Multi-frame validated detection.
            camera_id: Target Camera UUID string (defaults to settings.CAMERA_ID).
            bus_id: Target Bus UUID string (defaults to settings.BUS_ID).
            frame_prefix: Frame reference prefix (defaults to settings.FRAME_REFERENCE_PREFIX).
            latitude: Optional camera GPS latitude.
            longitude: Optional camera GPS longitude.

        Returns:
            True if ingested successfully (HTTP 201), False otherwise.
        """
        cam_id = camera_id or settings.CAMERA_ID
        b_id = bus_id or settings.BUS_ID
        f_prefix = frame_prefix or settings.FRAME_REFERENCE_PREFIX
        lat = latitude if latitude is not None else settings.CAMERA_LATITUDE
        lon = longitude if longitude is not None else settings.CAMERA_LONGITUDE

        # 1. Check duplicate-send cooldown policy
        if not self.duplicate_filter.can_send(detection.track_id, cam_id, detection.timestamp):
            logger.debug(
                "Duplicate send suppressed for track #%d on camera %s (cooldown active)",
                detection.track_id,
                cam_id,
            )
            return False

        # 2. Map class name to backend detection type
        backend_type = self.map_detection_type(detection.class_name)
        if backend_type is None:
            logger.debug(
                "Skipping unmapped class %r (not a registered municipal issue type)",
                detection.class_name,
            )
            return False

        # 3. Construct payload strictly matching DetectionCreate contract
        frame_ref = f"{f_prefix}/frame_{detection.frame_id:06d}"
        iso_detected_at = datetime.fromtimestamp(detection.timestamp, tz=timezone.utc).isoformat()

        payload: dict[str, Any] = {
            "bus_id": b_id,
            "camera_id": cam_id,
            "detection_type": backend_type,
            "confidence": round(detection.average_confidence, 4),
            "latitude": lat,
            "longitude": lon,
            "detected_at": iso_detected_at,
            "frame_reference": frame_ref,
            "metadata": {
                "track_id": detection.track_id,
                "class_name": detection.class_name,
                "class_id": detection.class_id,
                "frames_seen": detection.frames_seen,
                "first_seen_timestamp": detection.first_seen_timestamp,
                "last_seen_timestamp": detection.last_seen_timestamp,
                "bbox": detection.bbox.to_dict(),
                "validation_status": detection.validation_status,
            },
        }

        self.detections_attempted += 1
        req_start = time.perf_counter()

        # 4. HTTP POST execution with bounded retries
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._client.post(self._endpoint, json=payload)
                status_code = response.status_code

                # Success: 201 Created
                if status_code in (200, 201):
                    latency_ms = (time.perf_counter() - req_start) * 1000.0
                    self.total_request_latency_ms += latency_ms
                    self.detections_sent += 1
                    self.last_successful_send = time.time()
                    self.duplicate_filter.record_sent(detection.track_id, cam_id, detection.timestamp)
                    logger.info(
                        "Ingested detection %s [Track #%d | Latency: %.1f ms] -> %s",
                        backend_type,
                        detection.track_id,
                        latency_ms,
                        self._endpoint,
                    )
                    return True

                # Client Errors: 4xx (Do not retry, fail fast)
                if 400 <= status_code < 500:
                    latency_ms = (time.perf_counter() - req_start) * 1000.0
                    self.total_request_latency_ms += latency_ms
                    self.detections_failed += 1
                    logger.warning(
                        "Backend rejected detection with HTTP %d: %s",
                        status_code,
                        response.text,
                    )
                    return False

                # Server Errors: 5xx (Retryable)
                logger.warning(
                    "Backend error HTTP %d on attempt %d/%d for track #%d",
                    status_code,
                    attempt,
                    self.max_retries,
                    detection.track_id,
                )

            except (httpx.RequestError, httpx.TimeoutException) as net_err:
                logger.warning(
                    "Backend request failure (%s) on attempt %d/%d",
                    net_err.__class__.__name__,
                    attempt,
                    self.max_retries,
                )

            # Retry delay if attempts remain
            if attempt < self.max_retries:
                self.retry_count += 1
                if self.retry_delay_seconds > 0:
                    time.sleep(self.retry_delay_seconds)

        # All retries exhausted
        latency_ms = (time.perf_counter() - req_start) * 1000.0
        self.total_request_latency_ms += latency_ms
        self.detections_failed += 1
        logger.error(
            "Failed to ingest detection for track #%d after %d retries.",
            detection.track_id,
            self.max_retries,
        )
        return False

    def close(self) -> None:
        """Close underlying HTTP client resources."""
        self._client.close()
