"""Frame processing interface and concrete implementations."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from app.client.backend_client import BackendClient
from app.processing.detection_types import FrameDetections, TrackedDetection, ValidatedDetection
from app.processing.tracker import ObjectTracker
from app.processing.validator import MultiFrameValidator
from app.processing.yolo_detector import YOLODetector

logger = logging.getLogger(__name__)


class BaseFrameProcessor(ABC):
    """Abstract base class for all frame processors (YOLO / Computer Vision models)."""

    @abstractmethod
    def process_frame(
        self,
        frame: np.ndarray,
        frame_id: int,
        timestamp: float,
    ) -> dict[str, Any]:
        """
        Process a single sampled video frame.

        Args:
            frame: Raw BGR video frame from OpenCV (numpy array).
            frame_id: Monotonically increasing sampled frame index.
            timestamp: Unix epoch timestamp when the frame was acquired.

        Returns:
            Dictionary containing processing metadata or detections.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release processor resources."""
        raise NotImplementedError


class LoggingFrameProcessor(BaseFrameProcessor):
    """
    Phase 4A Frame Processor — logs frame reception and basic throughput metrics.
    Does not run neural network inference.
    """

    def __init__(self, log_interval: int = 50) -> None:
        self.log_interval = log_interval
        self.processed_count: int = 0
        self.start_time: float = time.time()

    def process_frame(
        self,
        frame: np.ndarray,
        frame_id: int,
        timestamp: float,
    ) -> dict[str, Any]:
        self.processed_count += 1
        height, width = frame.shape[:2]

        if self.processed_count % self.log_interval == 0:
            elapsed = time.time() - self.start_time
            fps = round(self.processed_count / elapsed, 2) if elapsed > 0 else 0.0
            logger.info(
                "Sampled frame #%d | Resolution: %dx%d | Total processed: %d | Throughput: %.1f FPS",
                frame_id,
                width,
                height,
                self.processed_count,
                fps,
            )

        return {
            "frame_id": frame_id,
            "resolution": (width, height),
            "timestamp": timestamp,
            "processed": True,
        }

    def close(self) -> None:
        """Clean shutdown hook."""
        logger.info("Closing LoggingFrameProcessor. Total frames handled: %d", self.processed_count)


class YOLOFrameProcessor(BaseFrameProcessor):
    """
    Phase 4D Frame Processor — orchestrates YOLO object detection, multi-object
    tracking, multi-frame validation, and HTTP ingestion into FastAPI.
    """

    def __init__(
        self,
        detector: YOLODetector,
        tracker: ObjectTracker | None = None,
        validator: MultiFrameValidator | None = None,
        backend_client: BackendClient | None = None,
        log_interval: int = 25,
    ) -> None:
        self.detector = detector
        self.tracker = tracker if tracker is not None else ObjectTracker()
        self.validator = validator if validator is not None else MultiFrameValidator()
        self.backend_client = backend_client
        self.log_interval = log_interval

        self.frames_inferred: int = 0
        self.raw_detection_count: int = 0
        self.tracked_detection_count: int = 0
        self.validated_detection_count: int = 0
        self.total_inference_time_ms: float = 0.0
        self.start_time: float = time.time()

    @property
    def processed_count(self) -> int:
        """Alias for frames_inferred to provide uniform processor interface."""
        return self.frames_inferred

    @property
    def total_detections(self) -> int:
        """Alias for raw_detection_count for backwards compatibility."""
        return self.raw_detection_count

    @property
    def active_track_count(self) -> int:
        """Current number of active object tracks."""
        return self.tracker.active_track_count

    @property
    def average_inference_time_ms(self) -> float:
        """Mean inference latency across all processed frames."""
        if self.frames_inferred <= 0:
            return 0.0
        return round(self.total_inference_time_ms / self.frames_inferred, 2)

    def process_frame(
        self,
        frame: np.ndarray,
        frame_id: int,
        timestamp: float,
    ) -> dict[str, Any]:
        # 1. Raw YOLO detection
        raw_results: FrameDetections = self.detector.detect(
            frame,
            frame_id=frame_id,
            timestamp=timestamp,
        )

        # 2. Object Tracking
        tracked: list[TrackedDetection] = self.tracker.update(
            detections=raw_results.detections,
            frame_id=frame_id,
            timestamp=timestamp,
        )

        # 3. Multi-Frame Validation
        validated: list[ValidatedDetection] = self.validator.validate(
            tracked_detections=tracked,
            active_tracks=self.tracker.active_tracks,
            frame_id=frame_id,
            timestamp=timestamp,
        )

        # 4. FastAPI Backend Ingestion (ONLY validated detections)
        if self.backend_client is not None:
            for val_det in validated:
                self.backend_client.send_detection(val_det)

        # Metrics accumulation
        self.frames_inferred += 1
        self.raw_detection_count += raw_results.count
        self.tracked_detection_count += len(tracked)
        self.validated_detection_count += len(validated)
        self.total_inference_time_ms += raw_results.inference_time_ms

        if self.frames_inferred % self.log_interval == 0:
            avg_latency = self.average_inference_time_ms
            logger.info(
                "Frame #%d | Raw detections: %d | Tracked: %d | Validated: %d | Active tracks: %d | Avg inference: %.1f ms",
                frame_id,
                raw_results.count,
                len(tracked),
                len(validated),
                self.active_track_count,
                avg_latency,
            )
            if self.backend_client is not None:
                logger.info(
                    "[BACKEND] Attempted: %d | Sent: %d | Failed: %d | Retries: %d | Avg latency: %.1f ms",
                    self.backend_client.detections_attempted,
                    self.backend_client.detections_sent,
                    self.backend_client.detections_failed,
                    self.backend_client.retry_count,
                    self.backend_client.average_backend_request_latency_ms,
                )

        return {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "inference_time_ms": round(raw_results.inference_time_ms, 2),
            "model_name": raw_results.model_name,
            "detection_count": raw_results.count,
            "count": raw_results.count,
            "raw_detections": [d.to_dict() for d in raw_results.detections],
            "detections": [d.to_dict() for d in raw_results.detections],
            "tracked_count": len(tracked),
            "tracked_detections": [t.to_dict() for t in tracked],
            "validated_count": len(validated),
            "validated_detections": [v.to_dict() for v in validated],
            "active_track_count": self.active_track_count,
            "backend_sent": self.backend_client.detections_sent if self.backend_client else 0,
            "backend_failed": self.backend_client.detections_failed if self.backend_client else 0,
        }

    def close(self) -> None:
        """Clean shutdown hook."""
        logger.info(
            "Closing YOLOFrameProcessor. Frames: %d | Raw: %d | Tracked: %d | Validated: %d | Active tracks: %d | Avg latency: %.2f ms",
            self.frames_inferred,
            self.raw_detection_count,
            self.tracked_detection_count,
            self.validated_detection_count,
            self.active_track_count,
            self.average_inference_time_ms,
        )
        if self.backend_client is not None:
            self.backend_client.close()
        self.tracker.reset()
        self.validator.reset()
        self.detector.close()
