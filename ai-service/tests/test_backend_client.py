"""Unit and integration tests for Phase 4D BackendClient and HTTP Ingestion."""

from __future__ import annotations

import time
import uuid
from unittest.mock import MagicMock
import httpx
import numpy as np
import pytest

from app.client.backend_client import (
    DEFAULT_DETECTION_TYPE_MAP,
    BackendClient,
    DuplicateSendFilter,
)
from app.processing.detection_types import (
    BoundingBox,
    Detection,
    FrameDetections,
    TrackedDetection,
    ValidatedDetection,
)
from app.processing.frame_processor import YOLOFrameProcessor
from app.processing.tracker import ObjectTracker
from app.processing.validator import MultiFrameValidator


@pytest.fixture
def sample_validated_detection() -> ValidatedDetection:
    """Fixture providing a realistic multi-frame validated vehicle detection."""
    return ValidatedDetection(
        track_id=42,
        class_id=2,
        class_name="car",
        confidence=0.88,
        average_confidence=0.88,
        bbox=BoundingBox(x1=100.0, y1=150.0, x2=300.0, y2=400.0),
        frame_id=10,
        timestamp=1700000003.0,
        frames_seen=4,
        first_seen_timestamp=1700000000.0,
        last_seen_timestamp=1700000003.0,
        validation_status="validated",
    )


class TestDuplicateSendFilter:
    """Tests for in-memory deduplication and cooldown enforcement."""

    def test_can_send_initially(self) -> None:
        filt = DuplicateSendFilter(cooldown_seconds=5.0)
        assert filt.can_send(track_id=1, camera_id="cam-1", current_timestamp=100.0) is True

    def test_cooldown_suppresses_subsequent_sends(self) -> None:
        filt = DuplicateSendFilter(cooldown_seconds=5.0)
        filt.record_sent(track_id=1, camera_id="cam-1", current_timestamp=100.0)

        # Immediate repeat within cooldown
        assert filt.can_send(track_id=1, camera_id="cam-1", current_timestamp=102.0) is False
        assert filt.can_send(track_id=1, camera_id="cam-1", current_timestamp=104.9) is False

        # After cooldown expired
        assert filt.can_send(track_id=1, camera_id="cam-1", current_timestamp=105.1) is True

    def test_different_track_or_camera_not_suppressed(self) -> None:
        filt = DuplicateSendFilter(cooldown_seconds=5.0)
        filt.record_sent(track_id=1, camera_id="cam-1", current_timestamp=100.0)

        # Different track on same camera
        assert filt.can_send(track_id=2, camera_id="cam-1", current_timestamp=101.0) is True

        # Same track on different camera
        assert filt.can_send(track_id=1, camera_id="cam-2", current_timestamp=101.0) is True


class TestBackendClient:
    """Tests for BackendClient HTTP transmission, contract compliance, and resilience."""

    def test_detection_type_mapping(self) -> None:
        client = BackendClient(base_url="http://localhost:8080")
        assert client.map_detection_type("car") == "VEHICLE"
        assert client.map_detection_type("bus") == "VEHICLE"
        assert client.map_detection_type("truck") == "VEHICLE"
        assert client.map_detection_type("motorcycle") == "VEHICLE"
        assert client.map_detection_type("bicycle") == "VEHICLE"
        assert client.map_detection_type("person") == "PEDESTRIAN"
        assert client.map_detection_type("pedestrian") == "PEDESTRIAN"
        assert client.map_detection_type("pothole") == "POTHOLE"
        assert client.map_detection_type("garbage") == "GARBAGE_DUMP"
        # Unknown/unmapped class
        assert client.map_detection_type("traffic_cone") is None

    def test_send_detection_successful_201(
        self, sample_validated_detection: ValidatedDetection
    ) -> None:
        mock_http = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": str(uuid.uuid4())}
        mock_http.post.return_value = mock_response

        client = BackendClient(
            base_url="http://localhost:8080",
            api_prefix="/api/v1",
            http_client=mock_http,
        )

        test_cam_id = str(uuid.uuid4())
        test_bus_id = str(uuid.uuid4())

        success = client.send_detection(
            detection=sample_validated_detection,
            camera_id=test_cam_id,
            bus_id=test_bus_id,
            latitude=12.9716,
            longitude=77.5946,
        )

        assert success is True
        assert client.detections_attempted == 1
        assert client.detections_sent == 1
        assert client.detections_failed == 0
        assert client.retry_count == 0
        assert client.last_successful_send is not None

        # Verify POST payload
        mock_http.post.assert_called_once()
        call_args = mock_http.post.call_args
        assert call_args[0][0] == "http://localhost:8080/api/v1/detections"
        payload = call_args[1]["json"]

        assert payload["bus_id"] == test_bus_id
        assert payload["camera_id"] == test_cam_id
        assert payload["detection_type"] == "VEHICLE"
        assert payload["confidence"] == 0.88
        assert payload["latitude"] == 12.9716
        assert payload["longitude"] == 77.5946
        assert "metadata" in payload
        assert payload["metadata"]["track_id"] == 42
        assert payload["metadata"]["class_name"] == "car"
        assert payload["metadata"]["validation_status"] == "validated"

    def test_send_detection_4xx_client_error_no_retry(
        self, sample_validated_detection: ValidatedDetection
    ) -> None:
        mock_http = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 422
        mock_response.text = '{"detail": "Validation error"}'
        mock_http.post.return_value = mock_response

        client = BackendClient(
            base_url="http://localhost:8080",
            max_retries=3,
            http_client=mock_http,
        )

        success = client.send_detection(sample_validated_detection)

        assert success is False
        # Client errors should fail fast without retrying
        assert mock_http.post.call_count == 1
        assert client.detections_attempted == 1
        assert client.detections_sent == 0
        assert client.detections_failed == 1
        assert client.retry_count == 0

    def test_send_detection_5xx_server_error_retries_and_exhausts(
        self, sample_validated_detection: ValidatedDetection
    ) -> None:
        mock_http = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        mock_http.post.return_value = mock_response

        client = BackendClient(
            base_url="http://localhost:8080",
            max_retries=3,
            retry_delay_seconds=0.001,
            http_client=mock_http,
        )

        success = client.send_detection(sample_validated_detection)

        assert success is False
        assert mock_http.post.call_count == 3
        assert client.detections_attempted == 1
        assert client.detections_sent == 0
        assert client.detections_failed == 1
        assert client.retry_count == 2

    def test_send_detection_timeout_retries_and_recovers(
        self, sample_validated_detection: ValidatedDetection
    ) -> None:
        mock_http = MagicMock(spec=httpx.Client)
        mock_success_response = MagicMock(spec=httpx.Response)
        mock_success_response.status_code = 201

        # First call times out, second call succeeds
        mock_http.post.side_effect = [
            httpx.ConnectTimeout("Connection timed out"),
            mock_success_response,
        ]

        client = BackendClient(
            base_url="http://localhost:8080",
            max_retries=3,
            retry_delay_seconds=0.001,
            http_client=mock_http,
        )

        success = client.send_detection(sample_validated_detection)

        assert success is True
        assert mock_http.post.call_count == 2
        assert client.detections_attempted == 1
        assert client.detections_sent == 1
        assert client.detections_failed == 0
        assert client.retry_count == 1

    def test_duplicate_cooldown_suppresses_send(
        self, sample_validated_detection: ValidatedDetection
    ) -> None:
        mock_http = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201
        mock_http.post.return_value = mock_response

        client = BackendClient(
            base_url="http://localhost:8080",
            cooldown_seconds=10.0,
            http_client=mock_http,
        )

        # First send succeeds
        first = client.send_detection(sample_validated_detection)
        assert first is True
        assert mock_http.post.call_count == 1

        # Second send within cooldown window suppressed
        second = client.send_detection(sample_validated_detection)
        assert second is False
        # HTTP client was NOT called again
        assert mock_http.post.call_count == 1

    def test_unmapped_class_skipped_cleanly(self) -> None:
        mock_http = MagicMock(spec=httpx.Client)
        client = BackendClient(base_url="http://localhost:8080", http_client=mock_http)

        det = ValidatedDetection(
            track_id=99,
            class_id=80,
            class_name="traffic_light",
            confidence=0.90,
            average_confidence=0.90,
            bbox=BoundingBox(x1=10.0, y1=10.0, x2=20.0, y2=20.0),
            frame_id=5,
            timestamp=105.0,
            frames_seen=5,
            first_seen_timestamp=100.0,
            last_seen_timestamp=105.0,
            validation_status="validated",
        )

        success = client.send_detection(det)
        assert success is False
        assert mock_http.post.call_count == 0


class TestPipelineHTTPIntegration:
    """Tests verifying YOLOFrameProcessor integration with BackendClient."""

    def test_pipeline_sends_only_validated_detections(self) -> None:
        """
        Verify that raw detections in frames 1-2 are NOT sent,
        and only upon validation in frame 3 is HTTP send triggered.
        """
        mock_detector = MagicMock()
        mock_client = MagicMock(spec=BackendClient)
        mock_client.detections_sent = 1
        mock_client.detections_failed = 0
        mock_client.detections_attempted = 1
        mock_client.retry_count = 0
        mock_client.average_backend_request_latency_ms = 12.5

        tracker = ObjectTracker(iou_threshold=0.50, max_age=5)
        validator = MultiFrameValidator(min_frames=3, window_frames=5, min_confidence=0.40)

        processor = YOLOFrameProcessor(
            detector=mock_detector,
            tracker=tracker,
            validator=validator,
            backend_client=mock_client,
            log_interval=1,
        )

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = BoundingBox(x1=50.0, y1=50.0, x2=150.0, y2=150.0)

        # Frame 1: Detection -> Not validated
        mock_detector.detect.return_value = FrameDetections(
            frame_id=1,
            timestamp=100.0,
            inference_time_ms=10.0,
            model_name="yolov8n.pt",
            detections=[Detection(class_id=2, class_name="car", confidence=0.85, bbox=bbox)],
        )
        res1 = processor.process_frame(fake_frame, frame_id=1, timestamp=100.0)
        assert res1["validated_count"] == 0
        mock_client.send_detection.assert_not_called()

        # Frame 2: Detection -> Not validated
        mock_detector.detect.return_value = FrameDetections(
            frame_id=2,
            timestamp=100.2,
            inference_time_ms=10.0,
            model_name="yolov8n.pt",
            detections=[Detection(class_id=2, class_name="car", confidence=0.87, bbox=bbox)],
        )
        res2 = processor.process_frame(fake_frame, frame_id=2, timestamp=100.2)
        assert res2["validated_count"] == 0
        mock_client.send_detection.assert_not_called()

        # Frame 3: Detection -> VALIDATED!
        mock_detector.detect.return_value = FrameDetections(
            frame_id=3,
            timestamp=100.4,
            inference_time_ms=10.0,
            model_name="yolov8n.pt",
            detections=[Detection(class_id=2, class_name="car", confidence=0.89, bbox=bbox)],
        )
        res3 = processor.process_frame(fake_frame, frame_id=3, timestamp=100.4)
        assert res3["validated_count"] == 1

        # send_detection MUST have been called exactly once
        mock_client.send_detection.assert_called_once()
        validated_arg = mock_client.send_detection.call_args[0][0]
        assert isinstance(validated_arg, ValidatedDetection)
        assert validated_arg.class_name == "car"
        assert validated_arg.frames_seen == 3

    def test_pipeline_offline_mode_without_backend_client(self) -> None:
        """Verify pipeline operates completely normally when backend_client is None."""
        mock_detector = MagicMock()
        tracker = ObjectTracker(iou_threshold=0.50, max_age=5)
        validator = MultiFrameValidator(min_frames=1, window_frames=5, min_confidence=0.40)

        processor = YOLOFrameProcessor(
            detector=mock_detector,
            tracker=tracker,
            validator=validator,
            backend_client=None,  # Offline mode
            log_interval=1,
        )

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = BoundingBox(x1=50.0, y1=50.0, x2=150.0, y2=150.0)

        mock_detector.detect.return_value = FrameDetections(
            frame_id=1,
            timestamp=100.0,
            inference_time_ms=10.0,
            model_name="yolov8n.pt",
            detections=[Detection(class_id=2, class_name="car", confidence=0.85, bbox=bbox)],
        )

        res = processor.process_frame(fake_frame, frame_id=1, timestamp=100.0)
        assert res["validated_count"] == 1
        assert res["backend_sent"] == 0
        assert res["backend_failed"] == 0

        # Close without error
        processor.close()
