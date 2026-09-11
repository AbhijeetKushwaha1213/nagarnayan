"""Tests for YOLOFrameProcessor integrating YOLODetector and metrics tracking."""

from __future__ import annotations

import time
from unittest.mock import MagicMock
import numpy as np
import pytest

from app.processing.detection_types import BoundingBox, Detection, FrameDetections
from app.processing.frame_processor import YOLOFrameProcessor


def test_yolo_frame_processor_delegation_and_metrics() -> None:
    """Verify that YOLOFrameProcessor delegates inference and updates metrics."""
    mock_detector = MagicMock()

    # Create dummy FrameDetections returned by detector
    fake_dets = FrameDetections(
        frame_id=1,
        timestamp=time.time(),
        detections=[
            Detection(
                class_id=0,
                class_name="person",
                confidence=0.88,
                bbox=BoundingBox(x1=10.0, y1=20.0, x2=50.0, y2=100.0),
            ),
            Detection(
                class_id=2,
                class_name="car",
                confidence=0.92,
                bbox=BoundingBox(x1=100.0, y1=200.0, x2=300.0, y2=400.0),
            ),
        ],
        inference_time_ms=15.5,
        model_name="yolov8n.pt",
    )
    mock_detector.detect.return_value = fake_dets

    processor = YOLOFrameProcessor(detector=mock_detector, log_interval=10)
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    res = processor.process_frame(fake_frame, frame_id=1, timestamp=fake_dets.timestamp)

    mock_detector.detect.assert_called_once_with(fake_frame, frame_id=1, timestamp=fake_dets.timestamp)
    assert res["frame_id"] == 1
    assert res["detection_count"] == 2
    assert len(res["detections"]) == 2
    assert res["detections"][0]["class_name"] == "person"
    assert res["detections"][1]["class_name"] == "car"
    assert res["inference_time_ms"] == 15.5

    assert processor.processed_count == 1
    assert processor.total_detections == 2
    assert processor.total_inference_time_ms == 15.5
    assert processor.average_inference_time_ms == 15.5

    # Process a second frame with 0 detections
    mock_detector.detect.return_value = FrameDetections(
        frame_id=2,
        timestamp=time.time(),
        detections=[],
        inference_time_ms=10.5,
        model_name="yolov8n.pt",
    )
    res2 = processor.process_frame(fake_frame, frame_id=2, timestamp=time.time())
    assert res2["detection_count"] == 0
    assert processor.processed_count == 2
    assert processor.total_detections == 2
    assert processor.total_inference_time_ms == 26.0
    assert processor.average_inference_time_ms == 13.0

    # Test close cleanup
    processor.close()
    mock_detector.close.assert_called_once()
