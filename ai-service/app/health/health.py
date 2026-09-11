"""Internal health and telemetry monitoring for RTSP stream readers."""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any


class StreamHealth:
    """Tracks operational metrics and connection health for a video stream."""

    def __init__(self) -> None:
        self.is_connected: bool = False
        self.total_frames_received: int = 0
        self.total_frames_sampled: int = 0
        self.last_frame_timestamp: float | None = None
        self.reconnect_count: int = 0
        self.connected_at: float | None = None
        self.disconnected_at: float | None = None

        # Throughput tracking
        self._fps_window_start: float = time.time()
        self._fps_window_frames: int = 0
        self.current_fps: float = 0.0

    def record_connected(self, connected: bool) -> None:
        now = time.time()
        if connected and not self.is_connected:
            self.connected_at = now
            self.disconnected_at = None
        elif not connected and self.is_connected:
            self.disconnected_at = now

        self.is_connected = connected

    def record_reconnect(self) -> None:
        self.reconnect_count += 1
        self.is_connected = False

    def record_frame_received(self) -> None:
        now = time.time()
        self.total_frames_received += 1
        self.last_frame_timestamp = now

        # Update running FPS over 2-second windows
        self._fps_window_frames += 1
        elapsed = now - self._fps_window_start
        if elapsed >= 2.0:
            self.current_fps = round(self._fps_window_frames / elapsed, 1)
            self._fps_window_start = now
            self._fps_window_frames = 0

    def record_frame_sampled(self) -> None:
        self.total_frames_sampled += 1

    def get_status(self) -> dict[str, Any]:
        """Return diagnostic metrics dictionary."""
        last_dt = (
            datetime.fromtimestamp(self.last_frame_timestamp, tz=timezone.utc).isoformat()
            if self.last_frame_timestamp is not None
            else None
        )
        uptime = (time.time() - self.connected_at) if (self.is_connected and self.connected_at) else 0.0

        return {
            "is_connected": self.is_connected,
            "total_frames_received": self.total_frames_received,
            "total_frames_sampled": self.total_frames_sampled,
            "last_frame_timestamp": self.last_frame_timestamp,
            "last_frame_iso": last_dt,
            "reconnect_count": self.reconnect_count,
            "current_fps": self.current_fps,
            "uptime_seconds": round(uptime, 1),
        }
