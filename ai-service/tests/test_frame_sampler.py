"""Unit tests for FrameSampler and SampledFrame metadata."""

from __future__ import annotations

from datetime import datetime, timezone
import numpy as np
import pytest

from app.processing.frame_sampler import FrameSampler, SampledFrame


def test_sampler_initialization() -> None:
    """Verify default and custom initialization values."""
    sampler = FrameSampler(
        sample_fps=5.0,
        bus_id="bus-101",
        camera_id="cam-001",
        stream_id="str-001",
    )
    assert sampler.sample_fps == 5.0
    assert sampler.sample_interval == pytest.approx(0.2, rel=1e-3)
    assert sampler.bus_id == "bus-101"
    assert sampler.camera_id == "cam-001"
    assert sampler.stream_id == "str-001"
    assert sampler.total_received == 0
    assert sampler.total_sampled == 0


def test_sampler_invalid_fps() -> None:
    """Verify that zero or negative sample FPS raises ValueError."""
    with pytest.raises(ValueError, match="strictly positive"):
        FrameSampler(sample_fps=0.0)

    with pytest.raises(ValueError, match="strictly positive"):
        FrameSampler(sample_fps=-2.0)


def test_frame_downsampling_30fps_to_5fps() -> None:
    """Simulate a 30 FPS video stream over 2 seconds (60 frames) sampled at 5 FPS."""
    sampler = FrameSampler(sample_fps=5.0)
    synthetic_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    sampled_frames: list[SampledFrame] = []
    base_time = 1725000000.0
    source_fps = 30.0
    frame_interval = 1.0 / source_fps

    for i in range(60):
        t = base_time + (i * frame_interval)
        result = sampler.sample(synthetic_frame, timestamp=t, source_fps=source_fps)
        if result is not None:
            sampled_frames.append(result)

    assert sampler.total_received == 60
    # Over 2 seconds at 5 FPS: expected ~10 sampled frames (at t=0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8)
    assert len(sampled_frames) in (10, 11)
    assert sampler.total_sampled == len(sampled_frames)


def test_sampled_frame_metadata_generation() -> None:
    """Verify that SampledFrame carries comprehensive metadata without disk persistence."""
    sampler = FrameSampler(
        sample_fps=2.0,
        bus_id="bus-abc",
        camera_id="cam-xyz",
        stream_id="str-123",
    )
    dummy_image = np.ones((480, 640, 3), dtype=np.uint8) * 128

    ts = 1725000010.0
    sampled = sampler.sample(dummy_image, timestamp=ts, source_fps=25.0)

    assert sampled is not None
    assert isinstance(sampled, SampledFrame)
    assert sampled.frame_number == 1
    assert sampled.raw_frame_number == 1
    assert sampled.width == 640
    assert sampled.height == 480
    assert sampled.source_fps == 25.0
    assert sampled.bus_id == "bus-abc"
    assert sampled.camera_id == "cam-xyz"
    assert sampled.stream_id == "str-123"
    assert isinstance(sampled.captured_at, datetime)
    assert sampled.captured_at.tzinfo == timezone.utc

    # Verify frame remains in memory as NumPy array
    assert sampled.frame is dummy_image
    assert sampled.shape == (480, 640, 3)

    # Verify to_metadata_dict
    meta = sampled.to_metadata_dict()
    assert meta["frame_number"] == 1
    assert meta["width"] == 640
    assert meta["height"] == 480
    assert meta["bus_id"] == "bus-abc"
    assert "frame" not in meta


def test_sampler_reset() -> None:
    """Verify reset resets counters and timestamps."""
    sampler = FrameSampler(sample_fps=5.0)
    dummy = np.zeros((10, 10, 3), dtype=np.uint8)

    sampler.sample(dummy, timestamp=1.0)
    sampler.sample(dummy, timestamp=1.01)
    assert sampler.total_received == 2
    assert sampler.total_sampled == 1

    sampler.reset()
    assert sampler.total_received == 0
    assert sampler.total_sampled == 0

    # Next frame at timestamp 2.0 should be sampled immediately
    res = sampler.sample(dummy, timestamp=2.0)
    assert res is not None
    assert res.frame_number == 1
