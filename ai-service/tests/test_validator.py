"""Unit tests for MultiFrameValidator component in Phase 3."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.detection.schemas import BoundingBox, TrackedDetection
from app.detection.tracker import Track
from app.validation.multi_frame_validator import MultiFrameValidator


def _make_tracked_detection(
    track_id: int,
    frame_number: int,
    confidence: float = 0.85,
    class_id: int = 2,
    class_name: str = "car",
) -> TrackedDetection:
    return TrackedDetection(
        class_id=class_id,
        class_name=class_name,
        confidence=confidence,
        bounding_box=BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=200.0),
        track_id=track_id,
        frame_number=frame_number,
        raw_frame_number=frame_number * 3,
        captured_at=datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc),
        bus_id="bus-001",
        camera_id="cam-001",
        stream_id="stream-001",
    )


def _make_track(
    track_id: int,
    first_seen: int,
    last_seen: int,
    obs_count: int,
    max_conf: float = 0.85,
) -> Track:
    return Track(
        track_id=track_id,
        class_id=2,
        class_name="car",
        first_seen_frame=first_seen,
        last_seen_frame=last_seen,
        observation_count=obs_count,
        max_confidence=max_conf,
        total_confidence=max_conf * obs_count,
        last_seen_timestamp=datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc),
        last_bbox=BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=200.0),
    )


def test_unvalidated_single_frame_detection() -> None:
    """8. Single-frame detection is NOT validated, even with very high confidence (0.95)."""
    validator = MultiFrameValidator(min_frames=3, window_frames=5, min_confidence=0.30)

    td = _make_tracked_detection(track_id=1, frame_number=1, confidence=0.95)
    active_tracks = {1: _make_track(1, 1, 1, 1, max_conf=0.95)}

    results = validator.validate([td], active_tracks, frame_number=1)

    assert results == []
    assert validator.validated_tracks_count == 0
    assert validator.validation_rejections == 1


def test_validated_multi_frame_detection_lifecycle() -> None:
    """9. Track appearing for min_frames (3) consecutive frames becomes validated on frame 3."""
    validator = MultiFrameValidator(min_frames=3, window_frames=5, min_confidence=0.30)

    # Frame 1: observation 1 -> unvalidated
    td1 = _make_tracked_detection(track_id=10, frame_number=1, confidence=0.80)
    trk = _make_track(10, 1, 1, 1, 0.80)
    res1 = validator.validate([td1], {10: trk}, frame_number=1)
    assert res1 == []
    assert not trk.validated

    # Frame 2: observation 2 -> unvalidated
    td2 = _make_tracked_detection(track_id=10, frame_number=2, confidence=0.85)
    trk = _make_track(10, 1, 2, 2, 0.85)
    res2 = validator.validate([td2], {10: trk}, frame_number=2)
    assert res2 == []
    assert not trk.validated

    # Frame 3: observation 3 -> VALIDATED!
    td3 = _make_tracked_detection(track_id=10, frame_number=3, confidence=0.90)
    trk = _make_track(10, 1, 3, 3, 0.90)
    res3 = validator.validate([td3], {10: trk}, frame_number=3)

    assert len(res3) == 1
    val = res3[0]
    assert val.track_id == 10
    assert val.validated is True
    assert val.first_seen_frame == 1
    assert val.last_seen_frame == 3
    assert val.observation_count == 3
    assert val.max_confidence == 0.90
    assert val.average_confidence == pytest.approx((0.80 + 0.85 + 0.90) / 3, abs=0.01)
    assert val.class_name == "car"
    assert val.bus_id == "bus-001"
    assert val.camera_id == "cam-001"
    assert val.stream_id == "stream-001"
    assert validator.validated_tracks_count == 1
    assert trk.validated is True


def test_confidence_threshold_rejection() -> None:
    """7. Track meeting frame count requirement but with average confidence below threshold is rejected."""
    validator = MultiFrameValidator(min_frames=3, window_frames=5, min_confidence=0.50)

    # 3 observations with confidence 0.40 (< min_confidence=0.50)
    for fn in (1, 2, 3):
        td = _make_tracked_detection(track_id=5, frame_number=fn, confidence=0.40)
        trk = _make_track(5, 1, fn, fn, 0.40)
        res = validator.validate([td], {5: trk}, frame_number=fn)

    # At frame 3, 3 observations exist, but avg_conf = 0.40 < 0.50 -> rejected
    assert res == []
    assert validator.validated_tracks_count == 0
    assert validator.validation_rejections == 3


def test_validation_sliding_window_expiration() -> None:
    """6. Sliding window drops stale observations outside window_frames."""
    validator = MultiFrameValidator(min_frames=3, window_frames=4, min_confidence=0.30)

    # Observed at frame 1 and 2
    for fn in (1, 2):
        td = _make_tracked_detection(track_id=7, frame_number=fn, confidence=0.85)
        trk = _make_track(7, 1, fn, fn, 0.85)
        validator.validate([td], {7: trk}, frame_number=fn)

    # Missed in frames 3, 4, 5, 6
    # At frame 7 (window 4 -> frames 4, 5, 6, 7), observations from frame 1 & 2 have expired!
    td7 = _make_tracked_detection(track_id=7, frame_number=7, confidence=0.85)
    trk = _make_track(7, 1, 7, 3, 0.85)
    res7 = validator.validate([td7], {7: trk}, frame_number=7)

    # In window [4..7], only frame 7 is present (1 observation < min_frames=3) -> not validated
    assert res7 == []
    assert len(validator.track_history[7]) == 1


def test_stale_track_cleanup() -> None:
    """10. Tracks evicted from active_tracks in tracker are purged from validator history."""
    validator = MultiFrameValidator(min_frames=3, window_frames=5, min_confidence=0.30)

    td = _make_tracked_detection(track_id=99, frame_number=1, confidence=0.85)
    trk = _make_track(99, 1, 1, 1, 0.85)
    validator.validate([td], {99: trk}, frame_number=1)
    assert 99 in validator.track_history

    # In subsequent frame, track 99 has expired from active_tracks (empty active_tracks)
    validator.validate([], {}, frame_number=2)
    assert 99 not in validator.track_history


def test_metadata_propagation_and_serialization() -> None:
    """11. Verify ValidatedDetection contains all metadata and serializes to dictionary cleanly."""
    validator = MultiFrameValidator(min_frames=2, window_frames=3, min_confidence=0.30)

    for fn in (1, 2):
        td = _make_tracked_detection(track_id=25, frame_number=fn, confidence=0.92)
        trk = _make_track(25, 1, fn, fn, 0.92)
        results = validator.validate([td], {25: trk}, frame_number=fn)

    assert len(results) == 1
    v = results[0]
    d = v.to_dict()

    assert d["track_id"] == 25
    assert d["class_name"] == "car"
    assert d["confidence"] == 0.92
    assert d["first_seen_frame"] == 1
    assert d["last_seen_frame"] == 2
    assert d["observation_count"] == 2
    assert d["max_confidence"] == 0.92
    assert d["average_confidence"] == 0.92
    assert d["validated"] is True
    assert d["bus_id"] == "bus-001"
    assert d["camera_id"] == "cam-001"
    assert d["stream_id"] == "stream-001"
    assert "bounding_box" in d
    assert d["bounding_box"]["x1"] == 100.0
