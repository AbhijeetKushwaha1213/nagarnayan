"""
AI Video Intelligence Service — Main Entry Point.

Phase 4: Validated Detection → Backend Ingestion.
Consumes RTSP stream, performs deterministic frame sampling, executes YOLO object detection,
maintains persistent ByteTrack identities, validates observations across temporal sliding windows,
transmits validated detections asynchronously to the FastAPI backend with bounded retries,
and manages operational diagnostics with clean shutdown.
"""

from __future__ import annotations

import logging
import signal
import sys
from typing import Any

from app.backend.client import BackendClient
from app.backend.detection_sender import DetectionSender
from app.core.config import settings
from app.core.logging import setup_logging
from app.detection.detector import YOLODetector
from app.detection.tracker import ObjectTracker
from app.processing.inference import InferenceProcessor
from app.streams.stream_manager import StreamManager
from app.validation.multi_frame_validator import MultiFrameValidator

logger = logging.getLogger("ai_service")


def main() -> None:
    """Initialize and run the RTSP stream ingestion, YOLO detection, tracking, validation, and backend sender service."""
    setup_logging(settings.LOG_LEVEL)

    logger.info("=" * 60)
    logger.info("Starting %s v%s (Phase 4: Validated Detection -> Backend Ingestion)", settings.SERVICE_NAME, settings.SERVICE_VERSION)
    logger.info("RTSP URL:            %s", settings.RTSP_URL)
    logger.info("Bus ID:              %s", settings.BUS_ID)
    logger.info("Camera ID:           %s", settings.CAMERA_ID)
    logger.info("Stream ID:           %s", settings.STREAM_ID or "(none)")
    logger.info("Sample FPS:          %.1f", settings.FRAME_SAMPLE_FPS)
    logger.info("YOLO Model:          %s", settings.YOLO_MODEL)
    logger.info("YOLO Device:         %s (configured: %s)", settings.resolved_device, settings.YOLO_DEVICE)
    logger.info("YOLO Conf Thresh:    %.2f", settings.YOLO_CONFIDENCE_THRESHOLD)
    logger.info("YOLO IoU Thresh:     %.2f", settings.YOLO_IOU_THRESHOLD)
    logger.info("YOLO Image Size:     %d", settings.YOLO_IMAGE_SIZE)
    logger.info("Tracking Enabled:    %s (type: %s, IoU: %.2f, max_age: %d)", settings.TRACKING_ENABLED, settings.TRACKER_TYPE, settings.TRACKING_IOU_THRESHOLD, settings.TRACK_MAX_AGE)
    logger.info("Validation:          min_frames=%d, window=%d, min_conf=%.2f", settings.VALIDATION_MIN_FRAMES, settings.VALIDATION_WINDOW_FRAMES, settings.VALIDATION_MIN_CONFIDENCE)
    logger.info("Backend Base URL:    %s", settings.BACKEND_BASE_URL)
    logger.info("Backend API Prefix:  %s", settings.BACKEND_API_PREFIX)
    logger.info("Backend Timeout:     %.1f seconds", settings.BACKEND_REQUEST_TIMEOUT_SECONDS)
    logger.info("Backend Retries:     %d (delay: %.1fs)", settings.BACKEND_MAX_RETRIES, settings.BACKEND_RETRY_DELAY_SECONDS)
    logger.info("Backend Queue Size:  %d", settings.BACKEND_QUEUE_MAX_SIZE)
    logger.info("Reconnect Delay:     %.1f seconds", settings.RECONNECT_DELAY_SECONDS)
    logger.info("Max Retries:         %s", settings.MAX_RECONNECT_ATTEMPTS or "Unlimited")
    logger.info("=" * 60)

    # Initialize YOLO detector, tracker, and validator components
    detector = YOLODetector(
        model_path=settings.YOLO_MODEL,
        conf_threshold=settings.YOLO_CONFIDENCE_THRESHOLD,
        iou_threshold=settings.YOLO_IOU_THRESHOLD,
        device=settings.resolved_device,
        image_size=settings.YOLO_IMAGE_SIZE,
    )

    tracker = ObjectTracker(
        enabled=settings.TRACKING_ENABLED,
        tracker_type=settings.TRACKER_TYPE,
        iou_threshold=settings.TRACKING_IOU_THRESHOLD,
        max_age=settings.TRACK_MAX_AGE,
    )

    validator = MultiFrameValidator(
        min_frames=settings.VALIDATION_MIN_FRAMES,
        window_frames=settings.VALIDATION_WINDOW_FRAMES,
        min_confidence=settings.VALIDATION_MIN_CONFIDENCE,
    )

    # Initialize Backend client and asynchronous non-blocking sender
    backend_client = BackendClient(
        base_url=settings.BACKEND_BASE_URL,
        api_prefix=settings.BACKEND_API_PREFIX,
        timeout_seconds=settings.BACKEND_REQUEST_TIMEOUT_SECONDS,
        max_retries=settings.BACKEND_MAX_RETRIES,
        retry_delay_seconds=settings.BACKEND_RETRY_DELAY_SECONDS,
        retry_backoff_base=settings.BACKEND_RETRY_BACKOFF_BASE,
    )

    detection_sender = DetectionSender(
        client=backend_client,
        max_queue_size=settings.BACKEND_QUEUE_MAX_SIZE,
        cooldown_seconds=settings.BACKEND_DUPLICATE_COOLDOWN_SECONDS,
        start_worker=True,
    )

    inference_processor = InferenceProcessor(
        detector=detector,
        tracker=tracker,
        validator=validator,
        sender=detection_sender,
    )

    # Initialize stream manager with attached inference processor
    manager = StreamManager(
        rtsp_url=settings.RTSP_URL,
        sample_fps=settings.FRAME_SAMPLE_FPS,
        reconnect_delay=settings.RECONNECT_DELAY_SECONDS,
        max_reconnect_attempts=settings.MAX_RECONNECT_ATTEMPTS,
        status_log_interval=settings.STATUS_LOG_INTERVAL_SECONDS,
        bus_id=settings.BUS_ID,
        camera_id=settings.CAMERA_ID,
        stream_id=settings.STREAM_ID,
        inference_processor=inference_processor,
    )

    def handle_signal(signum: int, frame: Any) -> None:
        signame = signal.Signals(signum).name
        logger.info("Received termination signal %s. Initiating graceful shutdown...", signame)
        manager.stop()
        detection_sender.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        manager.start()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received.")
    finally:
        manager.stop()
        detection_sender.stop()
        logger.info("Service shutdown cleanly.")


if __name__ == "__main__":
    main()
