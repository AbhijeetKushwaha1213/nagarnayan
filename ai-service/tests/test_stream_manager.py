"""Unit tests for RTSPReader, StreamManager, and health monitoring with mocked OpenCV capture."""

from __future__ import annotations

import time
from typing import Any
import cv2
import numpy as np
import pytest

from app.processing.frame_sampler import FrameSampler, SampledFrame
from app.streams.rtsp_reader import RTSPReader
from app.streams.stream_manager import StreamManager


class MockVideoCapture:
    """Mock OpenCV VideoCapture for unit testing without live RTSP feeds."""

    def __init__(
        self,
        is_opened: bool = True,
        width: int = 1280,
        height: int = 720,
        fps: float = 30.0,
        frame_count: int = 10,
        read_delay: float = 0.002,
    ) -> None:
        self._is_opened = is_opened
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_count = frame_count
        self.read_delay = read_delay
        self.frames_read = 0
        self.released = False

    def isOpened(self) -> bool:
        return self._is_opened and not self.released

    def set(self, prop: int, value: Any) -> bool:
        return True

    def get(self, prop: int) -> float:
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return float(self.width)
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(self.height)
        if prop == cv2.CAP_PROP_FPS:
            return float(self.fps)
        return 0.0

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self.isOpened() or self.frames_read >= self.frame_count:
            return False, None
        self.frames_read += 1
        if self.read_delay > 0:
            time.sleep(self.read_delay)
        frame = np.full((self.height, self.width, 3), fill_value=self.frames_read, dtype=np.uint8)
        return True, frame

    def release(self) -> None:
        self.released = True
        self._is_opened = False


def test_rtsp_reader_successful_connection() -> None:
    """Verify successful connection and property extraction."""
    mock_cap = MockVideoCapture(is_opened=True, width=1920, height=1080, fps=25.0)

    reader = RTSPReader(
        rtsp_url="rtsp://mock-host:8554/live",
        capture_factory=lambda url: mock_cap,
    )

    assert not reader.is_connected
    connected = reader.connect()

    assert connected is True
    assert reader.is_connected is True
    assert reader.width == 1920
    assert reader.height == 1080
    assert reader.source_fps == 25.0


def test_rtsp_reader_failed_connection() -> None:
    """Verify failed connection handling when capture cannot be opened."""
    mock_cap = MockVideoCapture(is_opened=False)

    reader = RTSPReader(
        rtsp_url="rtsp://unreachable-host:8554/live",
        capture_factory=lambda url: mock_cap,
    )

    connected = reader.connect()
    assert connected is False
    assert reader.is_connected is False
    assert reader.reconnect_count == 1
    assert mock_cap.released is True


def test_rtsp_reader_frame_reading_and_stream_drop() -> None:
    """Verify frame reading and graceful disconnection upon stream drop."""
    mock_cap = MockVideoCapture(is_opened=True, frame_count=2)

    reader = RTSPReader(
        rtsp_url="rtsp://mock-host:8554/live",
        capture_factory=lambda url: mock_cap,
    )
    reader.connect()

    # Read frame 1
    success1, frame1, ts1 = reader.read_frame()
    assert success1 is True
    assert frame1 is not None
    assert isinstance(ts1, float)

    # Read frame 2
    success2, frame2, ts2 = reader.read_frame()
    assert success2 is True
    assert frame2 is not None

    # Frame 3: stream ends
    success3, frame3, ts3 = reader.read_frame()
    assert success3 is False
    assert frame3 is None
    assert reader.is_connected is False
    assert mock_cap.released is True


def test_rtsp_reader_graceful_resource_release() -> None:
    """Verify close() cleans up all capture resources."""
    mock_cap = MockVideoCapture(is_opened=True)
    reader = RTSPReader(
        rtsp_url="rtsp://mock-host:8554/live",
        capture_factory=lambda url: mock_cap,
    )
    reader.connect()
    assert reader.is_connected is True

    reader.close()
    assert reader.is_connected is False
    assert mock_cap.released is True


def test_stream_manager_lifecycle_and_sampling() -> None:
    """Verify StreamManager reading loop, sampling, callback execution, and clean exit."""
    received_samples: list[SampledFrame] = []

    def on_sample(frame_meta: SampledFrame) -> None:
        received_samples.append(frame_meta)

    def mock_factory(url: str) -> MockVideoCapture:
        return MockVideoCapture(is_opened=True, frame_count=100, width=640, height=480, fps=30.0)

    reader = RTSPReader(
        rtsp_url="rtsp://mock-host:8554/bus/front",
        reconnect_delay=0.01,
        capture_factory=mock_factory,
    )

    sampler = FrameSampler(
        sample_fps=500.0,
        bus_id="bus-1",
        camera_id="cam-1",
        stream_id="str-1",
    )

    manager = StreamManager(
        rtsp_url="rtsp://mock-host:8554/bus/front",
        reconnect_delay=0.01,
        reader=reader,
        sampler=sampler,
        on_sampled_frame=on_sample,
    )

    # Run manager with target limit of 5 frames
    manager.start(max_frames=5)

    assert len(received_samples) == 5
    assert received_samples[0].bus_id == "bus-1"
    assert received_samples[0].camera_id == "cam-1"
    assert received_samples[0].width == 640
    assert received_samples[0].height == 480
    assert manager.health.total_frames_sampled == 5
    assert not manager.is_running


def test_stream_manager_reconnect_behavior() -> None:
    """Verify StreamManager reconnects after temporary failure."""
    attempts = 0

    def flaky_capture_factory(url: str) -> MockVideoCapture:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return MockVideoCapture(is_opened=False)
        return MockVideoCapture(is_opened=True, frame_count=100)

    reader = RTSPReader(
        rtsp_url="rtsp://flaky-host:8554/live",
        reconnect_delay=0.01,
        capture_factory=flaky_capture_factory,
    )

    sampler = FrameSampler(sample_fps=500.0)

    manager = StreamManager(
        rtsp_url="rtsp://flaky-host:8554/live",
        reconnect_delay=0.01,
        reader=reader,
        sampler=sampler,
    )

    manager.start(max_frames=2)

    assert attempts >= 2
    assert manager.health.reconnect_count >= 1
    assert manager.health.total_frames_sampled == 2


def test_stream_manager_max_reconnect_attempts_respected() -> None:
    """Verify StreamManager terminates when max_reconnect_attempts is reached."""
    reader = RTSPReader(
        rtsp_url="rtsp://dead-host:8554/live",
        reconnect_delay=0.01,
        capture_factory=lambda url: MockVideoCapture(is_opened=False),
    )

    manager = StreamManager(
        rtsp_url="rtsp://dead-host:8554/live",
        reconnect_delay=0.01,
        max_reconnect_attempts=2,
        reader=reader,
    )

    start_time = time.time()
    manager.start()
    elapsed = time.time() - start_time

    assert manager.health.reconnect_count == 2
    assert not manager.is_running
    assert elapsed < 5.0


def test_stream_manager_graceful_stop() -> None:
    """Verify stop() cleanly halts the loop and unsets running state."""
    mock_cap = MockVideoCapture(is_opened=True, frame_count=1000)

    reader = RTSPReader(
        rtsp_url="rtsp://mock-host:8554/live",
        reconnect_delay=0.01,
        capture_factory=lambda url: mock_cap,
    )

    manager = StreamManager(
        rtsp_url="rtsp://mock-host:8554/live",
        reconnect_delay=0.01,
        reader=reader,
    )

    manager.stop()
    assert not manager.is_running
