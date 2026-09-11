"""
Unit and integration tests for AI Service Phase 4 & Phase 4.1:
Validated Detection -> Backend Ingestion & Regression Verification.

Validates:
  - Correct payload generation (FastAPI DetectionCreate contract)
  - Zero fabricated GPS coordinates (latitude and longitude strictly None)
  - Deterministic frame_reference generation for backend deduplication
  - Detection type mapping (COCO classes -> backend types, unmapped skipped)
  - BackendClient async HTTP transmission (201 success, 4xx fast fail, 5xx retries, network errors)
  - DetectionSender bounded queue with non-blocking enqueue and drop policy
  - Source-aware duplicate track suppression within cooldown window
  - DetectionSender constructor clean signature (no unused identity arguments)
  - Backend URL endpoint configuration (http://localhost:8080/api/v1/detections)
  - Exact field-by-field compatibility with backend DetectionCreate schema
  - Real service startup component construction matching main.py
  - Graceful shutdown queue drain logging
  - Pipeline integration: ONLY validated detections reach the sender
  - Pipeline resilience under backend outage
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import importlib.util
import json
import logging
import queue
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import httpx
import numpy as np
import pytest

from app.backend.client import BackendClient
from app.backend.detection_sender import DetectionSender
from app.backend.mapping import (
    YOLO_CLASS_TO_BACKEND_DETECTION_TYPE,
    build_frame_reference,
    map_class_to_detection_type,
)
from app.backend.schemas import BackendDetectionPayload
from app.core.config import settings
from app.detection.detector import YOLODetector
from app.detection.schemas import BoundingBox, Detection, TrackedDetection, ValidatedDetection
from app.detection.tracker import ObjectTracker
from app.processing.frame_sampler import SampledFrame
from app.processing.inference import InferenceProcessor
from app.streams.stream_manager import StreamManager
from app.validation.multi_frame_validator import MultiFrameValidator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_validated_detection() -> ValidatedDetection:
    """Provides a realistic multi-frame validated vehicle detection."""
    bbox = BoundingBox(x1=100.0, y1=200.0, x2=350.0, y2=450.0)
    now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    td = TrackedDetection(
        class_id=2,
        class_name="car",
        confidence=0.92,
        bounding_box=bbox,
        track_id=101,
        frame_number=5,
        raw_frame_number=150,
        captured_at=now,
        bus_id="00000000-0000-0000-0000-000000000001",
        camera_id="00000000-0000-0000-0000-000000000002",
        stream_id="00000000-0000-0000-0000-000000000003",
    )
    return ValidatedDetection(
        tracked_detection=td,
        track_id=101,
        class_id=2,
        class_name="car",
        confidence=0.92,
        bounding_box=bbox,
        frame_number=5,
        raw_frame_number=150,
        captured_at=now,
        first_seen_frame=1,
        last_seen_frame=5,
        observation_count=4,
        max_confidence=0.95,
        average_confidence=0.91,
        validated=True,
        bus_id="00000000-0000-0000-0000-000000000001",
        camera_id="00000000-0000-0000-0000-000000000002",
        stream_id="00000000-0000-0000-0000-000000000003",
    )


@pytest.fixture
def sample_pedestrian_detection() -> ValidatedDetection:
    """Provides a realistic multi-frame validated pedestrian detection."""
    bbox = BoundingBox(x1=50.0, y1=80.0, x2=120.0, y2=260.0)
    now = datetime(2026, 9, 10, 12, 0, 1, tzinfo=timezone.utc)
    td = TrackedDetection(
        class_id=0,
        class_name="person",
        confidence=0.85,
        bounding_box=bbox,
        track_id=102,
        frame_number=6,
        raw_frame_number=155,
        captured_at=now,
        bus_id="00000000-0000-0000-0000-000000000001",
        camera_id="00000000-0000-0000-0000-000000000002",
        stream_id=None,
    )
    return ValidatedDetection(
        tracked_detection=td,
        track_id=102,
        class_id=0,
        class_name="person",
        confidence=0.85,
        bounding_box=bbox,
        frame_number=6,
        raw_frame_number=155,
        captured_at=now,
        first_seen_frame=2,
        last_seen_frame=6,
        observation_count=3,
        max_confidence=0.88,
        average_confidence=0.83,
        validated=True,
        bus_id="00000000-0000-0000-0000-000000000001",
        camera_id="00000000-0000-0000-0000-000000000002",
        stream_id=None,
    )


# ---------------------------------------------------------------------------
# Test Scenario A & B & C: Mapping, Payload, Frame Reference, Zero Fake GPS
# ---------------------------------------------------------------------------

class TestMappingAndPayloads:
    def test_coco_classes_to_backend_detection_types(self) -> None:
        """Verify standard COCO vehicle and pedestrian classes map cleanly."""
        assert map_class_to_detection_type("car") == "VEHICLE"
        assert map_class_to_detection_type("bus") == "VEHICLE"
        assert map_class_to_detection_type("truck") == "VEHICLE"
        assert map_class_to_detection_type("motorcycle") == "VEHICLE"
        assert map_class_to_detection_type("bicycle") == "VEHICLE"
        assert map_class_to_detection_type("person") == "PEDESTRIAN"

    def test_municipal_defect_classes_map(self) -> None:
        """Verify municipal defect classes map correctly."""
        assert map_class_to_detection_type("pothole") == "POTHOLE"
        assert map_class_to_detection_type("damaged_road") == "DAMAGED_ROAD"
        assert map_class_to_detection_type("waterlogging") == "WATERLOGGING"

    def test_unmapped_classes_return_none(self) -> None:
        """Verify arbitrary COCO classes (e.g. furniture, sports) are skipped."""
        assert map_class_to_detection_type("chair") is None
        assert map_class_to_detection_type("kite") is None
        assert map_class_to_detection_type("sports ball") is None
        assert map_class_to_detection_type("dog") is None

    def test_build_frame_reference_with_stream_id(self) -> None:
        """Deterministic frame_reference must follow <stream_id>:<raw_frame>:<track_id>:<type>."""
        ref = build_frame_reference(
            stream_id="stream-uuid-123",
            camera_id="camera-uuid-456",
            raw_frame_number=450,
            track_id=7,
            detection_type="VEHICLE",
        )
        assert ref == "stream-uuid-123:450:7:VEHICLE"

    def test_build_frame_reference_fallback_to_camera_id(self) -> None:
        """When stream_id is None, camera_id must be used as the source prefix."""
        ref = build_frame_reference(
            stream_id=None,
            camera_id="camera-uuid-456",
            raw_frame_number=200,
            track_id=12,
            detection_type="PEDESTRIAN",
        )
        assert ref == "camera-uuid-456:200:12:PEDESTRIAN"

    def test_payload_zero_fabricated_gps(self, sample_validated_detection: ValidatedDetection) -> None:
        """Verify that GPS coordinates are strictly None (never fabricated)."""
        sender = DetectionSender(client=MagicMock(), start_worker=False)
        payload = sender.build_payload(sample_validated_detection)

        assert payload is not None
        assert payload.latitude is None
        assert payload.longitude is None

        as_dict = payload.to_dict()
        assert as_dict["latitude"] is None
        assert as_dict["longitude"] is None
        assert as_dict["detection_type"] == "VEHICLE"
        assert as_dict["confidence"] == 0.92
        assert as_dict["frame_reference"] == "00000000-0000-0000-0000-000000000003:150:101:VEHICLE"
        assert as_dict["metadata"]["track_id"] == 101
        assert as_dict["metadata"]["class_name"] == "car"
        assert as_dict["metadata"]["observation_count"] == 4


# ---------------------------------------------------------------------------
# Test Scenario D, E, F, G: BackendClient Async HTTP Behaviors
# ---------------------------------------------------------------------------

class TestBackendClientHTTP:
    @pytest.mark.asyncio
    async def test_post_detection_success_201(self, sample_validated_detection: ValidatedDetection) -> None:
        """HTTP 201 Created returns True and increments backend_successes."""
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/detections"
            data = json.loads(request.content.decode("utf-8"))
            assert data["detection_type"] == "VEHICLE"
            assert data["latitude"] is None
            assert data["longitude"] is None
            return httpx.Response(201, json={"id": "det-uuid-999", "status": "created"})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = BackendClient(
                base_url="http://mock-backend:8080",
                api_prefix="/api/v1",
                http_client=http_client,
            )
            sender = DetectionSender(client=client, start_worker=False)
            payload = sender.build_payload(sample_validated_detection)
            assert payload is not None

            success, status, resp = await client.post_detection(payload)
            assert success is True
            assert status == 201
            assert client.backend_requests == 1
            assert client.backend_successes == 1
            assert client.backend_failures == 0

    @pytest.mark.asyncio
    async def test_post_detection_4xx_client_error_no_retry(self, sample_validated_detection: ValidatedDetection) -> None:
        """HTTP 422 Unprocessable Entity fails immediately with 0 retries."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(422, json={"detail": "Camera ID not found in database"})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = BackendClient(
                base_url="http://mock-backend:8080",
                api_prefix="/api/v1",
                max_retries=3,
                http_client=http_client,
            )
            sender = DetectionSender(client=client, start_worker=False)
            payload = sender.build_payload(sample_validated_detection)
            assert payload is not None

            success, status, err = await client.post_detection(payload)
            assert success is False
            assert status == 422
            # Must NOT retry client errors
            assert call_count == 1
            assert client.backend_requests == 1
            assert client.backend_failures == 1
            assert client.retry_count == 0

    @pytest.mark.asyncio
    async def test_post_detection_5xx_server_error_retries_and_exhausts(
        self, sample_validated_detection: ValidatedDetection
    ) -> None:
        """HTTP 500 retries up to max_retries with backoff, then records failure."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(500, text="Internal Database Error")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = BackendClient(
                base_url="http://mock-backend:8080",
                api_prefix="/api/v1",
                max_retries=2,
                retry_delay_seconds=0.01,  # Fast for tests
                http_client=http_client,
            )
            sender = DetectionSender(client=client, start_worker=False)
            payload = sender.build_payload(sample_validated_detection)
            assert payload is not None

            success, status, err = await client.post_detection(payload)
            assert success is False
            assert status == 500
            # 1 initial attempt + 2 retries = 3 attempts total
            assert call_count == 3
            assert client.backend_requests == 3
            assert client.backend_failures == 1
            assert client.retry_count == 2

    @pytest.mark.asyncio
    async def test_post_detection_network_timeout_recovers_on_retry(
        self, sample_validated_detection: ValidatedDetection
    ) -> None:
        """Network timeout on first attempt succeeds on retry."""
        attempt = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise httpx.ReadTimeout("Connection timed out")
            return httpx.Response(201, json={"status": "recovered"})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = BackendClient(
                base_url="http://mock-backend:8080",
                api_prefix="/api/v1",
                max_retries=2,
                retry_delay_seconds=0.01,
                http_client=http_client,
            )
            sender = DetectionSender(client=client, start_worker=False)
            payload = sender.build_payload(sample_validated_detection)
            assert payload is not None

            success, status, resp = await client.post_detection(payload)
            assert success is True
            assert status == 201
            assert attempt == 2
            assert client.backend_requests == 2
            assert client.backend_successes == 1
            assert client.retry_count == 1


# ---------------------------------------------------------------------------
# Test Scenario H: Bounded Queue Drop Policy & Duplicate Suppression
# ---------------------------------------------------------------------------

class TestDetectionSenderQueue:
    def test_bounded_queue_drop_policy(self, sample_validated_detection: ValidatedDetection) -> None:
        """When queue reaches capacity, newest detection is dropped without crashing."""
        sender = DetectionSender(
            client=MagicMock(),
            max_queue_size=3,
            start_worker=False,
        )

        # Fill queue to capacity (3 items)
        assert sender.enqueue(sample_validated_detection) is True
        assert sender.enqueue(sample_validated_detection) is True
        assert sender.enqueue(sample_validated_detection) is True
        assert sender.queue_size == 3

        # 4th item must be dropped per documented drop policy
        dropped = sender.enqueue(sample_validated_detection)
        assert dropped is False
        assert sender.queue_full_drops == 1
        assert sender.detections_failed == 1
        assert sender.queue_size == 3

    def test_duplicate_cooldown_suppression(self, sample_validated_detection: ValidatedDetection) -> None:
        """Second submission of the same track from the same source within cooldown is suppressed."""
        sender = DetectionSender(
            client=MagicMock(),
            cooldown_seconds=10.0,
            start_worker=False,
        )

        source_id = "00000000-0000-0000-0000-000000000003"
        now = 1000.0
        assert sender.should_suppress_duplicate(source_id=source_id, track_id=101, detection_type="VEHICLE", now=now) is False

        sender.record_submitted_track(source_id=source_id, track_id=101, detection_type="VEHICLE", now=now)

        # Within cooldown window (5 seconds later) -> True (suppress)
        assert sender.should_suppress_duplicate(source_id=source_id, track_id=101, detection_type="VEHICLE", now=now + 5.0) is True

        # Different track_id -> False (do not suppress)
        assert sender.should_suppress_duplicate(source_id=source_id, track_id=102, detection_type="VEHICLE", now=now + 5.0) is False

        # Different detection_type -> False
        assert sender.should_suppress_duplicate(source_id=source_id, track_id=101, detection_type="PEDESTRIAN", now=now + 5.0) is False

        # After cooldown window (11 seconds later) -> False (allow)
        assert sender.should_suppress_duplicate(source_id=source_id, track_id=101, detection_type="VEHICLE", now=now + 11.0) is False


# ---------------------------------------------------------------------------
# Phase 4.1 Regression Tests: A, B, C, D, E, F
# ---------------------------------------------------------------------------

class TestPhase41Regressions:
    def test_regression_a_sender_constructor_signature(self) -> None:
        """
        Regression Test A: Verify DetectionSender initializes cleanly with standard parameters,
        and does not require or accept redundant bus_id/camera_id/stream_id arguments.
        """
        mock_client = MagicMock(spec=BackendClient)
        sender = DetectionSender(
            client=mock_client,
            max_queue_size=50,
            cooldown_seconds=15.0,
            start_worker=False,
        )
        assert sender.client is mock_client
        assert sender.max_queue_size == 50
        assert sender.cooldown_seconds == 15.0
        assert sender.queue_size == 0

    def test_regression_b_source_aware_duplicate_suppression(self) -> None:
        """
        Regression Test B: Verify duplicate suppression identity is source-specific.
        Identical local track IDs from different cameras/streams must NOT suppress each other.
        """
        sender = DetectionSender(
            client=MagicMock(),
            cooldown_seconds=10.0,
            start_worker=False,
        )

        camera_a = "00000000-0000-0000-0000-000000000001"
        camera_b = "00000000-0000-0000-0000-000000000002"
        now = 1000.0

        # Record track 42 on Camera A
        sender.record_submitted_track(source_id=camera_a, track_id=42, detection_type="VEHICLE", now=now)

        # Same track 42 on Camera A is suppressed within cooldown
        assert sender.should_suppress_duplicate(source_id=camera_a, track_id=42, detection_type="VEHICLE", now=now + 3.0) is True

        # Crucial: Track 42 on Camera B is NOT suppressed!
        assert sender.should_suppress_duplicate(source_id=camera_b, track_id=42, detection_type="VEHICLE", now=now + 3.0) is False

    def test_regression_c_backend_url_and_endpoint(self) -> None:
        """
        Regression Test C: Verify correct default backend port (8080) and endpoint URL construction.
        """
        client = BackendClient()
        assert client.base_url == "http://localhost:8080"
        assert client.api_prefix == "/api/v1"
        assert client._endpoint == "http://localhost:8080/api/v1/detections"

    def test_regression_d_exact_detection_create_payload_compatibility(
        self, sample_validated_detection: ValidatedDetection
    ) -> None:
        """
        Regression Test D: Verify that BackendDetectionPayload.to_dict() produces a payload
        strictly compatible with the backend's DetectionCreate Pydantic schema.
        """
        sender = DetectionSender(client=MagicMock(), start_worker=False)
        payload = sender.build_payload(sample_validated_detection)
        assert payload is not None

        dict_payload = payload.to_dict()

        # Load backend DetectionCreate schema dynamically to ensure exact parity
        spec = importlib.util.spec_from_file_location(
            "backend_detection_schema",
            "/Users/abhijeetkushwaha/Hackathon/nagarnayan/backend/app/schemas/detection.py",
        )
        assert spec is not None and spec.loader is not None
        backend_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backend_mod)
        DetectionCreate = backend_mod.DetectionCreate
        DetectionCreate.model_rebuild(_types_namespace={"datetime": datetime, "uuid": uuid, "Any": Any})

        # Validate against backend Pydantic schema
        backend_obj = DetectionCreate(**dict_payload)
        assert str(backend_obj.bus_id) == "00000000-0000-0000-0000-000000000001"
        assert str(backend_obj.camera_id) == "00000000-0000-0000-0000-000000000002"
        assert str(backend_obj.stream_id) == "00000000-0000-0000-0000-000000000003"
        assert backend_obj.detection_type == "VEHICLE"
        assert backend_obj.confidence == 0.92
        assert backend_obj.latitude is None
        assert backend_obj.longitude is None
        assert backend_obj.event_id is None
        assert backend_obj.metadata["track_id"] == 101

    def test_regression_e_service_startup_construction(self) -> None:
        """
        Regression Test E: Verify real startup path — instantiate the exact components
        used in main.py without raising constructor or configuration errors.
        """
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
            start_worker=False,  # Don't start background thread during unit test
        )

        inference_processor = InferenceProcessor(
            detector=detector,
            tracker=tracker,
            validator=validator,
            sender=detection_sender,
        )

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

        assert manager.is_running is False
        assert detection_sender.queue_size == 0
        assert inference_processor.sender is detection_sender

    def test_regression_f_graceful_shutdown_drain_warning_logged(
        self, caplog: pytest.LogCaptureFixture, sample_validated_detection: ValidatedDetection
    ) -> None:
        """
        Regression Test F: Verify that when the queue has remaining items upon stop(),
        a warning is logged indicating the number of dropped detections.
        """
        caplog.set_level(logging.WARNING)
        sender = DetectionSender(client=MagicMock(), max_queue_size=10, start_worker=False)
        # Put an item in the queue
        sender.enqueue(sample_validated_detection)
        assert sender.queue_size == 1

        # Simulate shutdown with non-drained items
        sender.stop(timeout=0.1)

        # Check that warning was logged
        warning_found = any(
            "pending detections could not be drained" in record.message
            for record in caplog.records
        )
        assert warning_found, "Expected shutdown warning for undrained queue items"


# ---------------------------------------------------------------------------
# Test Scenario I, J, K: Full Pipeline Invariants & Fault Tolerance
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    def test_only_validated_detections_reach_sender(self) -> None:
        """
        Verify the architectural invariant:
        Raw detections and unvalidated tracks are NEVER enqueued; only validated detections are sent.
        """
        enqueued_items: list[ValidatedDetection] = []
        mock_sender = MagicMock(spec=DetectionSender)
        mock_sender.enqueue_batch.side_effect = lambda items: enqueued_items.extend(items)
        mock_sender.get_metrics.return_value = {
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

        now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
        mock_detector = MagicMock()
        mock_detector.track.return_value = [
            Detection(
                class_id=2,
                class_name="car",
                confidence=0.90,
                bounding_box=BoundingBox(10.0, 10.0, 50.0, 50.0),
                frame_number=1,
                captured_at=now,
                raw_frame_number=1,
            )
        ]

        validator = MultiFrameValidator(min_frames=3, window_frames=5, min_confidence=0.5)
        tracker = ObjectTracker(enabled=True, tracker_type="bytetrack.yaml")

        processor = InferenceProcessor(
            detector=mock_detector,
            tracker=tracker,
            validator=validator,
            sender=mock_sender,
        )

        dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)

        # Frame 1: Detected, tracked, but NOT validated (1 < 3)
        frame1 = SampledFrame(
            frame_number=1,
            captured_at=now,
            source_fps=30.0,
            width=640,
            height=480,
            frame=dummy_img,
            raw_frame_number=1,
        )
        processor.process_sampled_frame(frame1)
        assert len(enqueued_items) == 0  # Nothing enqueued!
        mock_sender.enqueue_batch.assert_not_called()

        # Frame 2: Detected, tracked, but NOT validated (2 < 3)
        frame2 = SampledFrame(
            frame_number=2,
            captured_at=now,
            source_fps=30.0,
            width=640,
            height=480,
            frame=dummy_img,
            raw_frame_number=2,
        )
        processor.process_sampled_frame(frame2)
        assert len(enqueued_items) == 0  # Still nothing enqueued!
        mock_sender.enqueue_batch.assert_not_called()

        # Frame 3: 3rd observation -> VALIDATED!
        frame3 = SampledFrame(
            frame_number=3,
            captured_at=now,
            source_fps=30.0,
            width=640,
            height=480,
            frame=dummy_img,
            raw_frame_number=3,
        )
        processor.process_sampled_frame(frame3)
        assert len(enqueued_items) == 1  # Exactly 1 validated detection enqueued!
        assert isinstance(enqueued_items[0], ValidatedDetection)
        assert enqueued_items[0].class_name == "car"

    def test_pipeline_resilience_under_backend_outage(self) -> None:
        """
        Verify that backend failure or network rejection NEVER crashes the video frame processing loop.
        """
        mock_sender = MagicMock(spec=DetectionSender)
        mock_sender.enqueue_batch.side_effect = Exception("Backend completely unreachable / down")
        mock_sender.get_metrics.return_value = {
            "detections_submitted": 0,
            "detections_failed": 5,
            "detections_skipped": 0,
            "queue_size": 100,
            "queue_full_drops": 5,
            "backend_requests": 10,
            "backend_successes": 0,
            "backend_failures": 10,
            "retry_count": 5,
            "last_backend_error": "ConnectionRefused",
        }

        mock_detector = MagicMock()
        mock_detector.track.return_value = []

        processor = InferenceProcessor(
            detector=mock_detector,
            sender=mock_sender,
        )

        dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
        now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
        frame = SampledFrame(
            frame_number=1,
            captured_at=now,
            source_fps=30.0,
            width=640,
            height=480,
            frame=dummy_img,
            raw_frame_number=1,
        )

        # Processing must complete normally without raising
        result = processor.process_sampled_frame(frame)
        assert result == []
        assert processor.frames_processed == 1
        assert processor.frames_failed == 0

        # Telemetry combines pipeline metrics with sender metrics
        metrics = processor.get_metrics()
        assert metrics["frames_processed"] == 1
        assert metrics["detections_failed"] == 5
        assert metrics["backend_failures"] == 10
