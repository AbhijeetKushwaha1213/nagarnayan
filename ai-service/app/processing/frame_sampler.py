"""Frame sampling abstraction and in-memory frame metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import numpy as np


@dataclass
class SampledFrame:
    """In-memory representation of a sampled video frame with contextual metadata."""

    frame_number: int
    captured_at: datetime
    source_fps: float
    width: int
    height: int
    bus_id: str | None = None
    camera_id: str | None = None
    stream_id: str | None = None
    frame: np.ndarray = field(repr=False, default_factory=lambda: np.zeros((1, 1, 3), dtype=np.uint8))
    raw_frame_number: int = 0

    @property
    def shape(self) -> tuple[int, int, int]:
        """Return frame shape as (height, width, channels)."""
        return self.frame.shape if self.frame is not None else (0, 0, 0)

    def to_metadata_dict(self) -> dict[str, Any]:
        """Return metadata summary suitable for logging or downstream detection metadata."""
        return {
            "frame_number": self.frame_number,
            "raw_frame_number": self.raw_frame_number,
            "captured_at": self.captured_at.isoformat(),
            "source_fps": round(self.source_fps, 2),
            "width": self.width,
            "height": self.height,
            "bus_id": self.bus_id,
            "camera_id": self.camera_id,
            "stream_id": self.stream_id,
        }


class FrameSampler:
    """
    Subsamples a high-frequency video stream (e.g. 30 FPS) down to a manageable target rate (e.g. 5 FPS).

    Does NOT write frames to disk; maintains frames strictly in memory for downstream AI analysis.
    """

    def __init__(
        self,
        sample_fps: float = 5.0,
        bus_id: str | None = None,
        camera_id: str | None = None,
        stream_id: str | None = None,
    ) -> None:
        if sample_fps <= 0.0:
            raise ValueError(f"sample_fps must be strictly positive, got {sample_fps}")

        self.sample_fps = float(sample_fps)
        self.sample_interval = 1.0 / self.sample_fps
        self.bus_id = bus_id
        self.camera_id = camera_id
        self.stream_id = stream_id

        self._last_sampled_timestamp: float = 0.0
        self._total_received: int = 0
        self._total_sampled: int = 0

    @property
    def total_received(self) -> int:
        return self._total_received

    @property
    def total_sampled(self) -> int:
        return self._total_sampled

    def should_sample(self, timestamp: float) -> bool:
        """
        Determine if the frame at the given timestamp should be sampled.

        Args:
            timestamp: Epoch timestamp of the current frame in seconds.

        Returns:
            True if elapsed time since last sample exceeds the sample interval.
        """
        if self._last_sampled_timestamp == 0.0:
            return True
        return (timestamp - self._last_sampled_timestamp) >= (self.sample_interval - 1e-4)

    def sample(
        self,
        frame: np.ndarray,
        timestamp: float | None = None,
        source_fps: float = 0.0,
        captured_at: datetime | None = None,
    ) -> SampledFrame | None:
        """
        Process an incoming raw frame and return a SampledFrame if selected by the sampling rate.

        Args:
            frame: NumPy image array.
            timestamp: Epoch timestamp in seconds.
            source_fps: Original FPS of the video stream.
            captured_at: Optional explicit datetime. If None, generated from timestamp or now(UTC).

        Returns:
            SampledFrame if sampled, None if skipped.
        """
        self._total_received += 1
        ts = timestamp if timestamp is not None else datetime.now(timezone.utc).timestamp()

        if not self.should_sample(ts):
            return None

        self._last_sampled_timestamp = ts
        self._total_sampled += 1

        if captured_at is None:
            captured_at = datetime.fromtimestamp(ts, tz=timezone.utc)

        h, w = frame.shape[:2] if frame is not None else (0, 0)

        return SampledFrame(
            frame_number=self._total_sampled,
            raw_frame_number=self._total_received,
            captured_at=captured_at,
            source_fps=source_fps,
            width=w,
            height=h,
            bus_id=self.bus_id,
            camera_id=self.camera_id,
            stream_id=self.stream_id,
            frame=frame,
        )

    def reset(self) -> None:
        """Reset sampler counters and timestamps."""
        self._last_sampled_timestamp = 0.0
        self._total_received = 0
        self._total_sampled = 0
