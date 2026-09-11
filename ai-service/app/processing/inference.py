"""
Sampled Frame Inference, Tracking, and Multi-Frame Validation Processor.

Consumes SampledFrame objects, executes YOLO object detection, tracks objects
with persistent IDs, validates tracks across multi-frame sliding windows,
and dispatches validated detections to the backend sender while gathering operational metrics.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
import logging
import time
from typing import Any

from app.backend.detection_sender import DetectionSender
from app.core.config import settings
from app.detection.detector import YOLODetector
from app.detection.schemas import Detection, TrackedDetection, ValidatedDetection
from app.detection.tracker import ObjectTracker
from app.processing.frame_sampler import SampledFrame
from app.validation.multi_frame_validator import MultiFrameValidator

logger = logging.getLogger(__name__)


class InferenceProcessor:
    """
    Consumes SampledFrame objects, executes YOLO object detection, maintains persistent track IDs,
    validates observations across multi-frame sliding windows, dispatches validated detections
    to the backend sender, and tracks operational telemetry.
    """

    def __init__(
        self,
        detector: YOLODetector | None = None,
        tracker: ObjectTracker | None = None,
        validator: MultiFrameValidator | None = None,
        sender: DetectionSender | None = None,
        on_detection: Callable[[list[Detection]], None] | None = None,
        on_tracked: Callable[[list[TrackedDetection]], None] | None = None,
        on_validated: Callable[[list[ValidatedDetection]], None] | None = None,
    ) -> None:
        self.detector = detector or YOLODetector(
            model_path=settings.YOLO_MODEL,
            conf_threshold=settings.YOLO_CONFIDENCE_THRESHOLD,
            iou_threshold=settings.YOLO_IOU_THRESHOLD,
            device=settings.resolved_device,
            image_size=settings.YOLO_IMAGE_SIZE,
        )
        self.tracker = tracker or ObjectTracker(
            enabled=settings.TRACKING_ENABLED,
            tracker_type=settings.TRACKER_TYPE,
            iou_threshold=settings.TRACKING_IOU_THRESHOLD,
            max_age=settings.TRACK_MAX_AGE,
        )
        self.validator = validator or MultiFrameValidator(
            min_frames=settings.VALIDATION_MIN_FRAMES,
            window_frames=settings.VALIDATION_WINDOW_FRAMES,
            min_confidence=settings.VALIDATION_MIN_CONFIDENCE,
        )
        self.sender = sender

        self.on_detection = on_detection
        self.on_tracked = on_tracked
        self.on_validated = on_validated

        # Internal state of most recent processing cycle
        self.last_raw_detections: list[Detection] = []
        self.last_tracked_detections: list[TrackedDetection] = []
        self.last_validated_detections: list[ValidatedDetection] = []

        # Inference performance telemetry
        self.frames_received: int = 0
        self.frames_processed: int = 0
        self.frames_failed: int = 0
        self.detections_total: int = 0
        self.inference_count: int = 0
        self.total_inference_time_ms: float = 0.0
        self.last_inference_time_ms: float = 0.0

    @property
    def average_inference_time_ms(self) -> float:
        """Calculate mean inference latency in milliseconds."""
        if self.inference_count == 0:
            return 0.0
        return round(self.total_inference_time_ms / self.inference_count, 1)

    def process_sampled_frame(self, sampled_frame: SampledFrame) -> list[TrackedDetection]:
        """
        Process an incoming sampled video frame through detection, tracking, validation,
        and backend transmission.

        Args:
            sampled_frame: SampledFrame carrying in-memory NumPy array and metadata.

        Returns:
            List of TrackedDetection objects for the current frame.
        """
        self.frames_received += 1

        if sampled_frame is None or sampled_frame.frame is None:
            self.frames_failed += 1
            logger.warning("Received invalid or None SampledFrame. Skipping processing.")
            return []

        t0 = time.perf_counter()

        # Step 1: YOLO Detection (using track() with ByteTrack if enabled)
        if settings.TRACKING_ENABLED:
            raw_detections = self.detector.track(
                frame=sampled_frame.frame,
                tracker=settings.TRACKER_TYPE,
                persist=True,
                frame_number=sampled_frame.frame_number,
                captured_at=sampled_frame.captured_at,
                bus_id=sampled_frame.bus_id,
                camera_id=sampled_frame.camera_id,
                stream_id=sampled_frame.stream_id,
                raw_frame_number=sampled_frame.raw_frame_number,
            )
        else:
            raw_detections = self.detector.predict(
                frame=sampled_frame.frame,
                frame_number=sampled_frame.frame_number,
                captured_at=sampled_frame.captured_at,
                bus_id=sampled_frame.bus_id,
                camera_id=sampled_frame.camera_id,
                stream_id=sampled_frame.stream_id,
                raw_frame_number=sampled_frame.raw_frame_number,
            )

        latency_ms = (time.perf_counter() - t0) * 1000.0

        # Step 2: Object Tracking (ByteTrack ingestion + IoU spatial fallback)
        tracked_detections = self.tracker.update(
            detections=raw_detections,
            frame_number=sampled_frame.frame_number,
            captured_at=sampled_frame.captured_at,
        )

        # Step 3: Multi-Frame Temporal Validation
        validated_detections = self.validator.validate(
            tracked_detections=tracked_detections,
            active_tracks=self.tracker.active_tracks,
            frame_number=sampled_frame.frame_number,
            timestamp=sampled_frame.captured_at,
        )

        # Step 4: Transmit ONLY Validated Detections to Backend Sender
        if self.sender is not None and validated_detections:
            self.sender.enqueue_batch(validated_detections)

        # Store last results
        self.last_raw_detections = raw_detections
        self.last_tracked_detections = tracked_detections
        self.last_validated_detections = validated_detections

        # Update telemetry
        self.last_inference_time_ms = round(latency_ms, 1)
        self.total_inference_time_ms += latency_ms
        self.inference_count += 1
        self.frames_processed += 1
        self.detections_total += len(raw_detections)

        # Log concise frame summary
        if raw_detections:
            counts = Counter(d.class_name for d in raw_detections)
            summary_str = ", ".join(f"{name}={count}" for name, count in counts.most_common())
            logger.info(
                "Frame %d: %s | tracked=%d, validated=%d | inference_time=%.1f ms",
                sampled_frame.frame_number,
                summary_str,
                len(tracked_detections),
                len(validated_detections),
                latency_ms,
            )
        else:
            logger.info(
                "Frame %d: no detections | inference_time=%.1f ms",
                sampled_frame.frame_number,
                latency_ms,
            )

        # Dispatch callbacks (only when detections exist)
        if self.on_detection is not None and raw_detections:
            try:
                self.on_detection(raw_detections)
            except Exception as cb_err:
                logger.error("Error in on_detection callback: %s", cb_err)

        if self.on_tracked is not None and tracked_detections:
            try:
                self.on_tracked(tracked_detections)
            except Exception as cb_err:
                logger.error("Error in on_tracked callback: %s", cb_err)

        if self.on_validated is not None and validated_detections:
            try:
                self.on_validated(validated_detections)
            except Exception as cb_err:
                logger.error("Error in on_validated callback: %s", cb_err)

        return tracked_detections

    def get_metrics(self) -> dict[str, Any]:
        """Expose combined inference, tracking, validation, and backend transmission telemetry."""
        tracker_metrics = self.tracker.get_metrics()
        validator_metrics = self.validator.get_metrics()
        sender_metrics = (
            self.sender.get_metrics()
            if self.sender is not None
            else {
                "detections_submitted": 0,
                "detections_failed": 0,
                "detections_skipped": 0,
                "queue_size": 0,
                "queue_full_drops": 0,
                "backend_requests": 0,
                "backend_successes": 0,
                "backend_failures": 0,
                "retry_count": 0,
                "last_backend_error": None,
            }
        )

        return {
            # Phase 2 metrics preserved
            "frames_received": self.frames_received,
            "frames_processed": self.frames_processed,
            "frames_failed": self.frames_failed,
            "detections_total": self.detections_total,
            "inference_count": self.inference_count,
            "last_inference_time_ms": self.last_inference_time_ms,
            "average_inference_time_ms": self.average_inference_time_ms,
            # Phase 3 metrics preserved
            "active_tracks": tracker_metrics["active_tracks"],
            "total_tracks_created": tracker_metrics["total_tracks_created"],
            "total_tracked_detections": tracker_metrics["total_tracked_detections"],
            "validated_tracks": validator_metrics["validated_tracks"],
            "validation_rejections": validator_metrics["validation_rejections"],
            # Phase 4 metrics added
            **sender_metrics,
        }
