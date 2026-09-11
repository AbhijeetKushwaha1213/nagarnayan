"""
Thread-safe detection sender service managing bounded worker queues and HTTP transmission.

Decouples the synchronous OpenCV frame capture loop from network I/O, ensuring that
backend HTTP latency, retries, or outages never block real-time video processing.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import queue
import threading
import time
from typing import Any

from app.backend.client import BackendClient
from app.backend.mapping import build_frame_reference, map_class_to_detection_type
from app.backend.schemas import BackendDetectionPayload
from app.core.config import settings
from app.detection.schemas import ValidatedDetection

logger = logging.getLogger(__name__)


class DetectionSender:
    """
    Thread-safe asynchronous transmission manager for validated detections.

    Guarantees:
      - Synchronous non-blocking enqueue method for the OpenCV capture thread
      - Thread-safe bounded in-memory queue with documented drop policy
      - Dedicated background worker thread driving an asyncio event loop for HTTP calls
      - In-process duplicate suppression with source-aware identity key (source_id, track_id, detection_type)
      - Graceful shutdown draining pending queue items within configurable timeout
      - Real-time operational telemetry tracking
    """

    def __init__(
        self,
        client: BackendClient | None = None,
        max_queue_size: int | None = None,
        cooldown_seconds: float | None = None,
        start_worker: bool = False,
    ) -> None:
        self.client = client or BackendClient()
        self.max_queue_size = int(
            max_queue_size
            if max_queue_size is not None
            else settings.BACKEND_QUEUE_MAX_SIZE
        )
        self.cooldown_seconds = float(
            cooldown_seconds
            if cooldown_seconds is not None
            else settings.BACKEND_DUPLICATE_COOLDOWN_SECONDS
        )

        # Thread-safe bounded queue for decoupling frame processing from HTTP latency
        self._queue: queue.Queue[ValidatedDetection] = queue.Queue(maxsize=self.max_queue_size)
        # Source-aware duplicate suppression key: (source_id, track_id, detection_type) -> timestamp
        self._submitted_tracks: dict[tuple[str, int, str], float] = {}

        # Worker thread management
        self._running: bool = False
        self._worker_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        # Telemetry metrics
        self.detections_submitted: int = 0
        self.detections_failed: int = 0
        self.detections_skipped: int = 0
        self.queue_full_drops: int = 0

        if start_worker:
            self.start()

    @property
    def queue_size(self) -> int:
        """Current number of detections waiting in the transmission queue."""
        return self._queue.qsize()

    def build_payload(self, detection: ValidatedDetection) -> BackendDetectionPayload | None:
        """
        Convert an internal ValidatedDetection into a BackendDetectionPayload.

        Returns:
            BackendDetectionPayload if class is mapped, None if unmapped.
        """
        detection_type = map_class_to_detection_type(detection.class_name)
        if detection_type is None:
            self.detections_skipped += 1
            return None

        bus_id = detection.bus_id or settings.BUS_ID
        camera_id = detection.camera_id or settings.CAMERA_ID
        stream_id = detection.stream_id or settings.STREAM_ID

        frame_ref = build_frame_reference(
            stream_id=stream_id,
            camera_id=camera_id,
            raw_frame_number=detection.raw_frame_number,
            track_id=detection.track_id,
            detection_type=detection_type,
        )

        iso_detected_at = (
            detection.captured_at.isoformat()
            if hasattr(detection.captured_at, "isoformat")
            else datetime.now(timezone.utc).isoformat()
        )

        # Encapsulate spatial and temporal observation data in metadata
        bbox_dict = (
            detection.bounding_box.to_dict()
            if hasattr(detection.bounding_box, "to_dict")
            else detection.bounding_box
        )
        metadata: dict[str, Any] = {
            "track_id": detection.track_id,
            "class_name": detection.class_name,
            "class_id": detection.class_id,
            "first_seen_frame": detection.first_seen_frame,
            "last_seen_frame": detection.last_seen_frame,
            "observation_count": detection.observation_count,
            "max_confidence": round(float(detection.max_confidence), 4),
            "average_confidence": round(float(detection.average_confidence), 4),
            "bounding_box": bbox_dict,
        }

        # Zero fabricated GPS coordinates: latitude and longitude are strictly None
        return BackendDetectionPayload(
            bus_id=bus_id,
            camera_id=camera_id,
            stream_id=stream_id,
            detection_type=detection_type,
            confidence=round(float(detection.confidence), 4),
            detected_at=iso_detected_at,
            frame_reference=frame_ref,
            metadata=metadata,
            latitude=None,
            longitude=None,
        )

    def should_suppress_duplicate(
        self,
        source_id: str,
        track_id: int,
        detection_type: str,
        now: float,
    ) -> bool:
        """
        Check if detection for this track has already been submitted within cooldown window.

        Identity is source-specific: (source_id, track_id, detection_type) to prevent identical
        local track IDs from different cameras/streams from suppressing each other.
        """
        key = (str(source_id), int(track_id), str(detection_type))
        last_sent = self._submitted_tracks.get(key)
        if last_sent is not None and (now - last_sent) < self.cooldown_seconds:
            return True
        return False

    def record_submitted_track(
        self,
        source_id: str,
        track_id: int,
        detection_type: str,
        now: float,
    ) -> None:
        """Record source-specific track submission timestamp for duplicate suppression."""
        key = (str(source_id), int(track_id), str(detection_type))
        self._submitted_tracks[key] = now
        # Clean up entries older than 2x cooldown to prevent memory leak
        cutoff = now - (self.cooldown_seconds * 2.0)
        stale_keys = [k for k, t in self._submitted_tracks.items() if t < cutoff]
        for k in stale_keys:
            del self._submitted_tracks[k]

    async def send_detection(self, detection: ValidatedDetection) -> bool:
        """
        Direct asynchronous submission of a single validated detection to the backend.

        Args:
            detection: ValidatedDetection object meeting multi-frame criteria.

        Returns:
            True if ingested successfully (or duplicate matched), False otherwise.
        """
        # 1. Map class and construct contract payload
        payload = self.build_payload(detection)
        if payload is None:
            return False

        # 2. In-process source-aware duplicate suppression check
        source_id = str(payload.stream_id or payload.camera_id)
        now = time.time()
        if self.should_suppress_duplicate(source_id, detection.track_id, payload.detection_type, now):
            self.detections_skipped += 1
            logger.debug(
                "Duplicate submission suppressed for source=%s, track=%d (%s)",
                source_id,
                detection.track_id,
                payload.detection_type,
            )
            return False

        # 3. Transmit to backend with bounded retries
        success, status_code, resp_text = await self.client.post_detection(payload)

        if success:
            self.detections_submitted += 1
            self.record_submitted_track(source_id, detection.track_id, payload.detection_type, now)
            return True
        else:
            self.detections_failed += 1
            return False

    def enqueue(self, detection: ValidatedDetection) -> bool:
        """
        Enqueue a validated detection non-blockingly from the synchronous frame capture loop.

        Documented Drop Policy:
          If the queue reaches capacity (max_queue_size), the newest detection is dropped,
          a warning is logged, and queue_full_drops is incremented. Frame processing is NEVER blocked.

        Returns:
            True if queued successfully, False if dropped due to queue congestion.
        """
        try:
            self._queue.put_nowait(detection)
            return True
        except queue.Full:
            self.queue_full_drops += 1
            self.detections_failed += 1
            logger.warning(
                "Backend ingestion queue full (size=%d). Dropped detection for track #%d (%s).",
                self.max_queue_size,
                detection.track_id,
                detection.class_name,
            )
            return False

    def enqueue_batch(self, detections: list[ValidatedDetection]) -> int:
        """Enqueue a list of validated detections. Returns count of successfully queued items."""
        queued = 0
        for d in detections:
            if self.enqueue(d):
                queued += 1
        return queued

    def start(self) -> None:
        """Start the background asynchronous worker thread if not already active."""
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._run_worker, daemon=True, name="BackendSenderWorker")
        self._worker_thread.start()
        logger.info("DetectionSender background worker started (queue maxsize=%d).", self.max_queue_size)

    def _run_worker(self) -> None:
        """Worker thread runner initializing an asyncio event loop to consume the queue."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._worker_consumer())
        finally:
            self._loop.run_until_complete(self.client.close())
            self._loop.close()

    async def _worker_consumer(self) -> None:
        """Asynchronous consumer task draining queue and invoking send_detection."""
        while self._running or not self._queue.empty():
            try:
                # Use non-blocking get with short sleep
                val_det = self._queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.05)
                continue

            try:
                await self.send_detection(val_det)
            except Exception as exc:
                logger.error("Error processing detection in sender worker: %s", exc)
            finally:
                self._queue.task_done()

    def stop(self, timeout: float = 2.0) -> None:
        """Gracefully stop background worker and wait for queue to drain."""
        if self._running:
            logger.info("Stopping DetectionSender background worker...")
            self._running = False
            if self._worker_thread is not None:
                self._worker_thread.join(timeout=timeout)
                self._worker_thread = None

        remaining = self._queue.qsize()
        if remaining > 0:
            logger.warning(
                "DetectionSender shutdown: %d pending detections could not be drained within timeout (%.1fs) and were dropped.",
                remaining,
                timeout,
            )
        logger.info("DetectionSender background worker stopped.")

    def get_metrics(self) -> dict[str, Any]:
        """Expose consolidated transmission telemetry."""
        client_m = self.client.get_metrics()
        return {
            "detections_submitted": self.detections_submitted,
            "detections_failed": self.detections_failed,
            "detections_skipped": self.detections_skipped,
            "queue_size": self.queue_size,
            "queue_full_drops": self.queue_full_drops,
            "backend_requests": client_m["backend_requests"],
            "backend_successes": client_m["backend_successes"],
            "backend_failures": client_m["backend_failures"],
            "retry_count": client_m["retry_count"],
            "last_backend_error": client_m["last_backend_error"],
        }
