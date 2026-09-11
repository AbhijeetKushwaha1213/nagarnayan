"""Tests for YOLODetector and DetectionResult types with mocked Ultralytics YOLO."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from app.processing.detection_types import BoundingBox, Detection, FrameDetections
from app.processing.yolo_detector import YOLODetector


def test_detection_types_serialization() -> None:
    """Verify serialization of BoundingBox, Detection, and FrameDetections."""
    bbox = BoundingBox(x1=10.5, y1=20.0, x2=100.5, y2=150.0)
    assert bbox.to_dict() == {"x1": 10.5, "y1": 20.0, "x2": 100.5, "y2": 150.0}

    det = Detection(class_id=0, class_name="pothole", confidence=0.91234, bbox=bbox)
    d_dict = det.to_dict()
    assert d_dict["class_id"] == 0
    assert d_dict["class_name"] == "pothole"
    assert d_dict["confidence"] == 0.9123
    assert d_dict["bbox"] == bbox.to_dict()

    frame_dets = FrameDetections(
        frame_id=42,
        timestamp=1000.0,
        detections=[det],
        inference_time_ms=35.5,
        model_name="models/best.pt",
    )
    f_dict = frame_dets.to_dict()
    assert f_dict["frame_id"] == 42
    assert f_dict["count"] == 1
    assert f_dict["inference_time_ms"] == 35.5
    assert len(f_dict["detections"]) == 1


class TestYOLODetector:

    @patch("app.processing.yolo_detector.YOLODetector._load_model")
    def test_device_resolution_auto_and_explicit(self, mock_load: MagicMock) -> None:
        mock_load.return_value = MagicMock()

        detector_cpu = YOLODetector(device="cpu")
        assert detector_cpu.resolved_device == "cpu"

        detector_cuda = YOLODetector(device="cuda")
        assert detector_cuda.resolved_device == "cuda"

        detector_auto = YOLODetector(device="auto")
        assert detector_auto.resolved_device in ("cuda", "mps", "cpu")

    @patch("app.processing.yolo_detector.YOLODetector._load_model")
    def test_detect_empty_results(self, mock_load: MagicMock) -> None:
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.boxes = []
        mock_model.predict.return_value = [mock_result]
        mock_load.return_value = mock_model

        detector = YOLODetector(model_path="test.pt")
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        res = detector.detect(fake_frame, frame_id=1, timestamp=100.0)
        assert res.frame_id == 1
        assert res.timestamp == 100.0
        assert res.count == 0
        assert len(res.detections) == 0
        assert res.inference_time_ms >= 0.0

    @patch("app.processing.yolo_detector.YOLODetector._load_model")
    def test_detect_multiple_objects(self, mock_load: MagicMock) -> None:
        # Create mocked boxes
        box1 = MagicMock()
        box1.xyxy = [[50.0, 60.0, 150.0, 200.0]]
        box1.conf = [0.92]
        box1.cls = [0]

        box2 = MagicMock()
        box2.xyxy = [[200.0, 100.0, 400.0, 300.0]]
        box2.conf = [0.85]
        box2.cls = [2]

        mock_result = MagicMock()
        mock_result.boxes = [box1, box2]
        mock_result.names = {0: "pothole", 2: "car"}

        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_result]
        mock_model.names = mock_result.names
        mock_load.return_value = mock_model

        detector = YOLODetector(model_path="models/best.pt")
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        res = detector.detect(fake_frame, frame_id=10, timestamp=500.0)
        assert res.frame_id == 10
        assert res.count == 2
        assert res.detections[0].class_name == "pothole"
        assert res.detections[0].confidence == 0.92
        assert res.detections[0].bbox.x1 == 50.0
        assert res.detections[1].class_name == "car"
        assert res.detections[1].confidence == 0.85

    @patch("app.processing.yolo_detector.YOLODetector._load_model")
    def test_close_releases_model(self, mock_load: MagicMock) -> None:
        mock_load.return_value = MagicMock()
        detector = YOLODetector(model_path="test.pt")
        assert detector.model is not None

        detector.close()
        assert detector.model is None
