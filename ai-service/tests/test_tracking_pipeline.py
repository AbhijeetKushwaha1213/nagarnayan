"""Integration tests for the full Phase 3 YOLO + Tracking + Validation pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import numpy as np
import pytest

from app.detection.detector import YOLODetector
from app.detection.schemas import BoundingBox, Detection, TrackedDetection, ValidatedDetection
from app.detection.tracker import ObjectTracker
from app.processing.frame_sampler import SampledFrame
from app.processing.inference import InferenceProcessor
from app.validation.multi_frame_validator import MultiFrameValidator


class MockBox:
    def __init__(self, xyxy: list[float], conf: float, cls_id: int) -> None:
        self.xyxy = [xyxy]
        self.conf = [conf]
        self.cls = [cls_id]


class MockBoxes:
    def __init__(self, boxes: list[MockBox]) -> None:
        self._boxes = boxes

    def __len__(self) -> int:
        return len(self._boxes)

    def __getitem__(self, idx: int) -> MockBox:
        return self._boxes[idx]


class MockResult:
    def __init__(self, boxes: list[MockBox] | None = None) -> None:
        self.boxes = MockBoxes(boxes) if boxes is not None else None
        self.names = {0: "person", 2: "car", 5: "bus"}


class MockYOLOModel:
    def __init__(self, box_sequence: list[list[MockBox]]) -> None:
        self.box_sequence = box_sequence
        self.call_count = 0
        self.names = {0: "person", 2: "car", 5: "bus"}

    def predict(self, **kwargs: Any) -> list[Any]:
        if self.call_count < len(self.box_sequence):
            boxes = self.box_sequence[self.call_count]
        else:
            boxes = []
        self.call_count += 1
        return [MockResult(boxes=boxes)]

    def track(self, **kwargs: Any) -> list[Any]:
        return self.predict(**kwargs)


def test_full_pipeline_raw_tracked_validated_lifecycle() -> None:
    """
    Test full pipeline transition:
    Frame 1: Car detected -> Assigned Track 1 -> Not Validated (obs=1 < 3)
    Frame 2: Car detected -> Persistent Track 1 -> Not Validated (obs=2 < 3)
    Frame 3: Car detected -> Persistent Track 1 -> VALIDATED! (obs=3 >= 3)
    Frame 4: Car disappears -> Track remains active (unseen=1 <= 30)
    """
    # 3 frames of car at roughly same location
    box_seq = [
        [MockBox([100.0, 100.0, 200.0, 200.0], 0.88, 2)],
        [MockBox([102.0, 101.0, 202.0, 201.0], 0.90, 2)],
        [MockBox([105.0, 102.0, 205.0, 202.0], 0.92, 2)],
        [],  # frame 4: empty
    ]
    mock_model = MockYOLOModel(box_seq)
    detector = YOLODetector(model_instance=mock_model)
    tracker = ObjectTracker(iou_threshold=0.50, max_age=5)
    validator = MultiFrameValidator(min_frames=3, window_frames=5, min_confidence=0.30)

    validated_events: list[list[ValidatedDetection]] = []
    processor = InferenceProcessor(
        detector=detector,
        tracker=tracker,
        validator=validator,
        on_validated=lambda v: validated_events.append(v),
    )

    t0 = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    # Frame 1
    f1 = SampledFrame(
        frame_number=1,
        raw_frame_number=1,
        captured_at=t0,
        source_fps=30.0,
        width=640,
        height=480,
        bus_id="bus-alpha",
        camera_id="cam-front",
        stream_id="stream-1",
        frame=np.zeros((480, 640, 3), dtype=np.uint8),
    )
    tracked1 = processor.process_sampled_frame(f1)
    assert len(tracked1) == 1
    tid = tracked1[0].track_id
    assert tid > 0
    assert len(processor.last_validated_detections) == 0
    assert len(validated_events) == 0

    # Frame 2
    f2 = SampledFrame(
        frame_number=2,
        raw_frame_number=2,
        captured_at=t0,
        source_fps=30.0,
        width=640,
        height=480,
        bus_id="bus-alpha",
        camera_id="cam-front",
        stream_id="stream-1",
        frame=np.zeros((480, 640, 3), dtype=np.uint8),
    )
    tracked2 = processor.process_sampled_frame(f2)
    assert len(tracked2) == 1
    assert tracked2[0].track_id == tid
    assert len(processor.last_validated_detections) == 0
    assert len(validated_events) == 0

    # Frame 3
    f3 = SampledFrame(
        frame_number=3,
        raw_frame_number=3,
        captured_at=t0,
        source_fps=30.0,
        width=640,
        height=480,
        bus_id="bus-alpha",
        camera_id="cam-front",
        stream_id="stream-1",
        frame=np.zeros((480, 640, 3), dtype=np.uint8),
    )
    tracked3 = processor.process_sampled_frame(f3)
    assert len(tracked3) == 1
    assert tracked3[0].track_id == tid
    assert len(processor.last_validated_detections) == 1
    assert len(validated_events) == 1

    val = processor.last_validated_detections[0]
    assert val.track_id == tid
    assert val.validated is True
    assert val.observation_count == 3
    assert val.first_seen_frame == 1
    assert val.last_seen_frame == 3
    assert val.class_name == "car"
    assert val.bus_id == "bus-alpha"

    # Frame 4: Disappears
    f4 = SampledFrame(
        frame_number=4,
        raw_frame_number=4,
        captured_at=t0,
        source_fps=30.0,
        width=640,
        height=480,
        bus_id="bus-alpha",
        camera_id="cam-front",
        stream_id="stream-1",
        frame=np.zeros((480, 640, 3), dtype=np.uint8),
    )
    tracked4 = processor.process_sampled_frame(f4)
    assert len(tracked4) == 0
    assert len(processor.last_validated_detections) == 0

    # Verify telemetry
    metrics = processor.get_metrics()
    assert metrics["frames_received"] == 4
    assert metrics["frames_processed"] == 4
    assert metrics["total_tracks_created"] == 1
    assert metrics["validated_tracks"] == 1
    assert metrics["total_tracked_detections"] == 3
    assert metrics["active_tracks"] == 1
