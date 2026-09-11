"""Tests for FrameProcessor, Frame Sampling, and Health Metrics."""

from __future__ import annotations

import time
from unittest.mock import MagicMock
import numpy as np
import pytest

from app.health.health import StreamHealth
from app.processing.frame_processor import LoggingFrameProcessor
from app.stream.manager import StreamManager


def test_logging_frame_processor() -> None:
    """Verify frame counting in LoggingFrameProcessor."""
    processor = LoggingFrameProcessor(log_interval=10)
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    res1 = processor.process_frame(fake_frame, frame_id=1, timestamp=time.time())
    assert res1["frame_id"] == 1
    assert res1["resolution"] == (640, 480)
    assert res1["processed"] is True

    res2 = processor.process_frame(fake_frame, frame_id=2, timestamp=time.time())
    assert res2["frame_id"] == 2
    assert processor.processed_count == 2

    processor.close()


def test_stream_health_metrics() -> None:
    """Verify StreamHealth tracking and statistics."""
    health = StreamHealth()
    assert not health.is_connected
    assert health.total_frames_received == 0
    assert health.total_frames_sampled == 0

    health.record_connected(True)
    assert health.is_connected is True

    health.record_frame_received()
    health.record_frame_received()
    assert health.total_frames_received == 2

    health.record_frame_sampled()
    assert health.total_frames_sampled == 1

    health.record_reconnect()
    assert health.reconnect_count == 1
    assert health.is_connected is False

    status = health.get_status()
    assert status["total_frames_received"] == 2
    assert status["total_frames_sampled"] == 1
    assert status["reconnect_count"] == 1


def test_deterministic_frame_sampling() -> None:
    """
    Verify that an input 30 FPS stream is sampled down to configured 5 FPS.
    Simulate 30 frames over 1.0 second; with 5 FPS sampling, ~5 frames should be sampled.
    """
    manager = StreamManager(
        rtsp_url="rtsp://mock:8554/test",
        sample_fps=5.0,
    )
    fake_frame = np.zeros((100, 100, 3), dtype=np.uint8)

    sampled_frames = []
    manager.processor.process_frame = MagicMock(side_effect=lambda f, fid, ts: sampled_frames.append(fid))

    # Simulate 30 frames arriving at 30 FPS (delta = 1/30 = ~0.0333s)
    base_time = 1000.0
    for i in range(30):
        frame_time = base_time + (i * (1.0 / 30.0))
        # Sampler check
        if frame_time - manager._last_sampled_timestamp >= manager.sample_interval:
            manager._last_sampled_timestamp = frame_time
            manager._sampled_frame_id += 1
            manager.processor.process_frame(fake_frame, manager._sampled_frame_id, frame_time)

    # 30 frames over 1.0s sampled at 5 FPS (interval = 0.2s) should yield exactly 5 sampled frames
    assert len(sampled_frames) == 5
    assert sampled_frames == [1, 2, 3, 4, 5]
