"""Unit tests for YOLODetector and InferenceProcessor with mocked model execution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import numpy as np
import pytest

from app.detection.detector import YOLODetector
from app.detection.schemas import BoundingBox, Detection
from app.processing.frame_sampler import SampledFrame
from app.processing.inference import InferenceProcessor


class MockBox:
    """Mock Ultralytics Results box element."""

    def __init__(self, xyxy: list[float], conf: float, cls_id: int) -> None:
        self.xyxy = [xyxy]
        self.conf = [conf]
        self.cls = [cls_id]


class MockBoxes:
    """Collection of MockBox items."""

    def __init__(self, boxes: list[MockBox]) -> None:
        self._boxes = boxes

    def __len__(self) -> int:
        return len(self._boxes)

    def __getitem__(self, idx: int) -> MockBox:
        return self._boxes[idx]


class MockResult:
    """Mock Ultralytics Result object."""

    def __init__(self, boxes: list[MockBox] | None = None, names: dict[int, str] | None = None) -> None:
        self.boxes = MockBoxes(boxes) if boxes is not None else None
        self.names = names or {0: "person", 1: "bicycle", 2: "car", 5: "bus", 7: "truck"}


class MockYOLOModel:
    """Mock YOLO model for deterministic offline testing."""

    def __init__(self, return_results: list[Any] | None = None, should_raise: bool = False) -> None:
        self.return_results = return_results
        self.should_raise = should_raise
        self.predict_calls: list[dict[str, Any]] = []
        self.names = {0: "person", 1: "bicycle", 2: "car", 5: "bus", 7: "truck"}

    def predict(self, **kwargs: Any) -> list[Any]:
        self.predict_calls.append(kwargs)
        if self.should_raise:
            raise RuntimeError("Mock inference hardware failure!")
        if self.return_results is not None:
            return self.return_results
        return [MockResult()]


def test_detector_initialization() -> None:
    """Verify detector parameters, defaults, and thresholds."""
    detector = YOLODetector(
        model_path="custom_yolo.pt",
        conf_threshold=0.35,
        iou_threshold=0.55,
        device="cpu",
        image_size=512,
    )
    assert detector.model_path == "custom_yolo.pt"
    assert detector.conf_threshold == 0.35
    assert detector.iou_threshold == 0.55
    assert detector.device == "cpu"
    assert detector.image_size == 512
    assert not detector.is_loaded


def test_cpu_device_configuration() -> None:
    """Verify CPU device setting is preserved."""
    detector = YOLODetector(device="cpu")
    assert detector.device == "cpu"


def test_invalid_frame_handling() -> None:
    """Verify None, empty, or corrupt frames return empty detections without raising errors."""
    mock_model = MockYOLOModel()
    detector = YOLODetector(model_instance=mock_model)

    # None frame
    assert detector.predict(None) == []

    # Empty array
    assert detector.predict(np.array([])) == []

    # 1D array
    assert detector.predict(np.zeros((10,))) == []

    # No predict calls made on mock model for invalid frames
    assert len(mock_model.predict_calls) == 0


def test_yolo_result_to_detection_conversion() -> None:
    """Verify extraction of bounding boxes, classes, confidence, and metadata."""
    boxes = [
        MockBox(xyxy=[10.0, 20.0, 110.0, 120.0], conf=0.88, cls_id=2),
        MockBox(xyxy=[200.5, 150.0, 350.2, 300.0], conf=0.72, cls_id=0),
    ]
    mock_model = MockYOLOModel(return_results=[MockResult(boxes=boxes)])
    detector = YOLODetector(model_instance=mock_model, conf_threshold=0.25)

    now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    detections = detector.predict(
        frame=synthetic_frame,
        frame_number=15,
        captured_at=now,
        bus_id="bus-101",
        camera_id="cam-001",
        stream_id="stream-001",
        raw_frame_number=45,
    )

    assert len(detections) == 2

    # Detection 1: car
    d1 = detections[0]
    assert d1.class_id == 2
    assert d1.class_name == "car"
    assert d1.confidence == pytest.approx(0.88, rel=1e-3)
    assert d1.bounding_box.x1 == 10.0
    assert d1.bounding_box.y1 == 20.0
    assert d1.bounding_box.x2 == 110.0
    assert d1.bounding_box.y2 == 120.0
    assert d1.bounding_box.width == 100.0
    assert d1.bounding_box.height == 100.0
    assert d1.frame_number == 15
    assert d1.raw_frame_number == 45
    assert d1.bus_id == "bus-101"
    assert d1.camera_id == "cam-001"
    assert d1.stream_id == "stream-001"
    assert d1.captured_at == now

    # Detection 2: person
    d2 = detections[1]
    assert d2.class_id == 0
    assert d2.class_name == "person"
    assert d2.confidence == pytest.approx(0.72, rel=1e-3)

    # Verify dictionary serialization
    d1_dict = d1.to_dict()
    assert d1_dict["class_name"] == "car"
    assert d1_dict["bounding_box"]["x1"] == 10.0


def test_confidence_filtering() -> None:
    """Verify detections below confidence threshold are discarded."""
    boxes = [
        MockBox(xyxy=[0, 0, 10, 10], conf=0.90, cls_id=2),  # keep
        MockBox(xyxy=[0, 0, 10, 10], conf=0.40, cls_id=0),  # discard (conf < 0.50)
        MockBox(xyxy=[0, 0, 10, 10], conf=0.55, cls_id=5),  # keep
    ]
    mock_model = MockYOLOModel(return_results=[MockResult(boxes=boxes)])
    detector = YOLODetector(model_instance=mock_model, conf_threshold=0.50)

    synthetic_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    detections = detector.predict(synthetic_frame)

    assert len(detections) == 2
    assert [d.class_name for d in detections] == ["car", "bus"]


def test_empty_yolo_results() -> None:
    """Verify empty detection results are handled gracefully."""
    mock_model = MockYOLOModel(return_results=[MockResult(boxes=[])])
    detector = YOLODetector(model_instance=mock_model)

    synthetic_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    detections = detector.predict(synthetic_frame)
    assert detections == []


def test_inference_error_handling() -> None:
    """Verify inference exception does not crash caller and returns empty list."""
    failing_model = MockYOLOModel(should_raise=True)
    detector = YOLODetector(model_instance=failing_model)

    synthetic_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    detections = detector.predict(synthetic_frame, frame_number=99)
    assert detections == []


def test_inference_processor_metrics_and_metadata_propagation() -> None:
    """Verify InferenceProcessor executes detector, attaches SampledFrame metadata, and updates metrics."""
    boxes = [MockBox(xyxy=[5, 5, 25, 25], conf=0.85, cls_id=2)]
    mock_model = MockYOLOModel(return_results=[MockResult(boxes=boxes)])
    detector = YOLODetector(model_instance=mock_model)

    dispatched_detections: list[list[Detection]] = []
    processor = InferenceProcessor(
        detector=detector,
        on_detection=lambda d: dispatched_detections.append(d),
    )

    frame_dt = datetime(2026, 9, 10, 12, 30, 0, tzinfo=timezone.utc)
    sampled_frame = SampledFrame(
        frame_number=7,
        raw_frame_number=35,
        captured_at=frame_dt,
        source_fps=30.0,
        width=1280,
        height=720,
        bus_id="bus-omega",
        camera_id="cam-front",
        stream_id="str-main",
        frame=np.zeros((720, 1280, 3), dtype=np.uint8),
    )

    results = processor.process_sampled_frame(sampled_frame)

    assert len(results) == 1
    assert results[0].frame_number == 7
    assert results[0].raw_frame_number == 35
    assert results[0].bus_id == "bus-omega"
    assert results[0].camera_id == "cam-front"
    assert results[0].stream_id == "str-main"
    assert results[0].class_name == "car"
    assert len(dispatched_detections) == 1

    # Verify performance metrics
    metrics = processor.get_metrics()
    assert metrics["frames_received"] == 1
    assert metrics["frames_processed"] == 1
    assert metrics["frames_failed"] == 0
    assert metrics["detections_total"] == 1
    assert metrics["inference_count"] == 1
    assert metrics["last_inference_time_ms"] >= 0.0
    assert metrics["average_inference_time_ms"] >= 0.0
