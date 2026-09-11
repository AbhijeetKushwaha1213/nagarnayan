"""Unit tests for ObjectTracker component in Phase 3."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.detection.schemas import BoundingBox, Detection
from app.detection.tracker import ObjectTracker


def test_tracker_stable_track_id_across_frames() -> None:
    """1. Track ID persistence across consecutive frames with spatial movement."""
    tracker = ObjectTracker(iou_threshold=0.40, max_age=10)
    t0 = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    # Frame 1: Car at (100, 100, 200, 200)
    det1 = Detection(
        class_id=2,
        class_name="car",
        confidence=0.88,
        bounding_box=BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=200.0),
        frame_number=1,
        captured_at=t0,
    )
    tracked1 = tracker.update([det1], frame_number=1, captured_at=t0)
    assert len(tracked1) == 1
    initial_id = tracked1[0].track_id
    assert initial_id > 0
    assert tracker.active_track_count == 1

    # Frame 2: Car moves slightly to (105, 102, 205, 202) -> high IoU
    det2 = Detection(
        class_id=2,
        class_name="car",
        confidence=0.92,
        bounding_box=BoundingBox(x1=105.0, y1=102.0, x2=205.0, y2=202.0),
        frame_number=2,
        captured_at=t0,
    )
    tracked2 = tracker.update([det2], frame_number=2, captured_at=t0)
    assert len(tracked2) == 1
    assert tracked2[0].track_id == initial_id
    assert tracker.active_tracks[initial_id].observation_count == 2
    assert tracker.active_tracks[initial_id].last_seen_frame == 2

    # Frame 3: Car moves slightly to (110, 105, 210, 205)
    det3 = Detection(
        class_id=2,
        class_name="car",
        confidence=0.90,
        bounding_box=BoundingBox(x1=110.0, y1=105.0, x2=210.0, y2=205.0),
        frame_number=3,
        captured_at=t0,
    )
    tracked3 = tracker.update([det3], frame_number=3, captured_at=t0)
    assert len(tracked3) == 1
    assert tracked3[0].track_id == initial_id
    assert tracker.active_tracks[initial_id].observation_count == 3
    assert tracker.active_tracks[initial_id].last_seen_frame == 3
    assert tracker.active_tracks[initial_id].average_confidence == pytest.approx(0.90, abs=0.01)


def test_tracker_new_object_receives_new_track_id() -> None:
    """2. New object in different location receives a separate, distinct track ID."""
    tracker = ObjectTracker(iou_threshold=0.50, max_age=10)
    t0 = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    # Frame 1: Person on left
    det1 = Detection(
        class_id=0,
        class_name="person",
        confidence=0.85,
        bounding_box=BoundingBox(x1=10.0, y1=10.0, x2=50.0, y2=80.0),
        frame_number=1,
        captured_at=t0,
    )
    # Frame 1: Bus on right
    det2 = Detection(
        class_id=5,
        class_name="bus",
        confidence=0.95,
        bounding_box=BoundingBox(x1=300.0, y1=200.0, x2=600.0, y2=450.0),
        frame_number=1,
        captured_at=t0,
    )

    tracked = tracker.update([det1, det2], frame_number=1, captured_at=t0)
    assert len(tracked) == 2
    assert tracked[0].track_id != tracked[1].track_id
    assert tracker.active_track_count == 2
    assert tracker.total_tracks_created == 2


def test_tracker_object_leaving_frame_and_expiration() -> None:
    """3. Object leaving the frame is tolerated up to max_age, then pruned cleanly."""
    tracker = ObjectTracker(iou_threshold=0.50, max_age=3)
    t0 = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    # Frame 1: Object present
    det = Detection(
        class_id=2,
        class_name="car",
        confidence=0.90,
        bounding_box=BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=200.0),
        frame_number=1,
        captured_at=t0,
    )
    res = tracker.update([det], frame_number=1, captured_at=t0)
    tid = res[0].track_id
    assert tid in tracker.active_tracks

    # Frames 2, 3, 4: Object disappears (gap = 1, 2, 3 <= max_age=3)
    for fn in (2, 3, 4):
        tracker.update([], frame_number=fn, captured_at=t0)
        assert tid in tracker.active_tracks
        assert tracker.active_tracks[tid].frames_unseen == (fn - 1)

    # Frame 5: gap = 5 - 1 = 4 > max_age(3) -> track must be pruned
    tracker.update([], frame_number=5, captured_at=t0)
    assert tid not in tracker.active_tracks
    assert tracker.active_track_count == 0


def test_tracker_temporary_missed_detection_recovers() -> None:
    """4. Temporary missed detection (1-2 frames) preserves track state and reassociates."""
    tracker = ObjectTracker(iou_threshold=0.40, max_age=5)
    t0 = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    # Frame 1: Car seen
    det1 = Detection(
        class_id=2,
        class_name="car",
        confidence=0.91,
        bounding_box=BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=200.0),
        frame_number=1,
        captured_at=t0,
    )
    res1 = tracker.update([det1], frame_number=1, captured_at=t0)
    tid = res1[0].track_id

    # Frame 2: Missed detection (e.g. occlusion or lighting flicker)
    tracker.update([], frame_number=2, captured_at=t0)
    assert tid in tracker.active_tracks
    assert tracker.active_tracks[tid].frames_unseen == 1

    # Frame 3: Car reappears at overlapping position
    det3 = Detection(
        class_id=2,
        class_name="car",
        confidence=0.89,
        bounding_box=BoundingBox(x1=102.0, y1=101.0, x2=202.0, y2=201.0),
        frame_number=3,
        captured_at=t0,
    )
    res3 = tracker.update([det3], frame_number=3, captured_at=t0)
    assert len(res3) == 1
    assert res3[0].track_id == tid
    assert tracker.active_tracks[tid].observation_count == 2
    assert tracker.active_tracks[tid].frames_unseen == 0


def test_tracker_native_track_id_ingestion() -> None:
    """Verify that native Ultralytics track_id is ingested directly."""
    tracker = ObjectTracker(iou_threshold=0.50, max_age=10)
    t0 = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    det = Detection(
        class_id=5,
        class_name="bus",
        confidence=0.96,
        bounding_box=BoundingBox(x1=50.0, y1=50.0, x2=300.0, y2=250.0),
        track_id=88,
        frame_number=1,
        captured_at=t0,
    )
    res = tracker.update([det], frame_number=1, captured_at=t0)
    assert res[0].track_id == 88
    assert 88 in tracker.active_tracks
    assert tracker.active_tracks[88].class_name == "bus"
    assert tracker.total_tracks_created == 1


def test_tracker_telemetry_metrics() -> None:
    """Verify tracker telemetry reporting."""
    tracker = ObjectTracker(iou_threshold=0.50, max_age=10)
    t0 = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    det1 = Detection(
        class_id=0,
        class_name="person",
        confidence=0.85,
        bounding_box=BoundingBox(x1=10.0, y1=10.0, x2=50.0, y2=80.0),
        frame_number=1,
        captured_at=t0,
    )
    tracker.update([det1], frame_number=1, captured_at=t0)

    metrics = tracker.get_metrics()
    assert metrics["active_tracks"] == 1
    assert metrics["total_tracks_created"] == 1
    assert metrics["total_tracked_detections"] == 1

    tracker.reset()
    assert tracker.get_metrics()["active_tracks"] == 0
    assert tracker.get_metrics()["total_tracks_created"] == 0
