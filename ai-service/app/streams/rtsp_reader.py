"""RTSP stream reader abstraction using OpenCV with mockable capture and TCP transport."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _default_capture_factory(rtsp_url: str) -> Any:
    """Default factory creating a real cv2.VideoCapture with TCP transport."""
    # Enforce TCP transport to eliminate UDP packet loss and video artifacting
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    capture = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    # Minimize internal buffer to 1 frame to eliminate latency
    try:
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    return capture


class RTSPReader:
    """
    Connects to an RTSP video stream and reads frames continuously.

    Responsibilities:
      - Open the stream using OpenCV (or injected capture factory)
      - Enforce low-latency buffering (buffer_size=1) and TCP transport
      - Expose frame dimensions (width, height) and source FPS
      - Detect stream disconnects and errors cleanly
      - Safely release all video resources
    """

    def __init__(
        self,
        rtsp_url: str,
        reconnect_delay: float = 5.0,
        timeout_seconds: float = 10.0,
        max_reconnect_attempts: int | None = None,
        capture_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.rtsp_url = rtsp_url
        self.reconnect_delay = max(0.1, float(reconnect_delay))
        self.timeout_seconds = max(0.5, float(timeout_seconds))
        self.max_reconnect_attempts = max_reconnect_attempts
        self._capture_factory = capture_factory or _default_capture_factory

        self._capture: Any | None = None
        self._is_connected: bool = False
        self.width: int = 0
        self.height: int = 0
        self.source_fps: float = 0.0
        self.reconnect_count: int = 0

    @property
    def is_connected(self) -> bool:
        """Check if capture is open and active."""
        if not self._is_connected or self._capture is None:
            return False
        try:
            return bool(self._capture.isOpened())
        except Exception:
            return False

    def connect(self) -> bool:
        """
        Open connection to the RTSP stream.

        Returns:
            True if connection was opened successfully, False otherwise.
        """
        self.disconnect()

        logger.info("Connecting to RTSP stream: %s", self.rtsp_url)

        try:
            capture = self._capture_factory(self.rtsp_url)

            if capture is None or not capture.isOpened():
                logger.warning("Failed to open RTSP stream at %s", self.rtsp_url)
                if capture is not None:
                    try:
                        capture.release()
                    except Exception:
                        pass
                self.reconnect_count += 1
                return False

            self._capture = capture
            self._is_connected = True

            # Extract source resolution and FPS
            try:
                self.width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                self.height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                self.source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            except Exception as prop_err:
                logger.debug("Could not read capture properties: %s", prop_err)
                self.width = 0
                self.height = 0
                self.source_fps = 0.0

            logger.info(
                "RTSP stream connected successfully [%dx%d @ %.1f FPS]",
                self.width,
                self.height,
                self.source_fps,
            )
            return True

        except Exception as exc:
            logger.error("Exception occurred while connecting to RTSP stream: %s", exc)
            self.disconnect()
            self.reconnect_count += 1
            return False

    def read_frame(self) -> tuple[bool, np.ndarray | None, float]:
        """
        Read the next video frame from the active stream.

        Returns:
            Tuple of (success: bool, frame: np.ndarray | None, timestamp: float)
        """
        timestamp = time.time()

        if not self.is_connected:
            return False, None, timestamp

        try:
            assert self._capture is not None
            ret, frame = self._capture.read()

            if not ret or frame is None or getattr(frame, "size", 0) == 0:
                logger.warning("Failed to retrieve frame from stream (connection dropped or ended)")
                self.disconnect()
                return False, None, timestamp

            return True, frame, timestamp

        except Exception as exc:
            logger.error("Error reading frame from RTSP stream: %s", exc)
            self.disconnect()
            return False, None, timestamp

    def disconnect(self) -> None:
        """Safely release the underlying capture handle."""
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception as exc:
                logger.debug("Exception while releasing capture handle: %s", exc)
            finally:
                self._capture = None

        self._is_connected = False

    @property
    def stream_width(self) -> int:
        """Alias for width."""
        return self.width

    @property
    def stream_height(self) -> int:
        """Alias for height."""
        return self.height

    @property
    def stream_fps(self) -> float:
        """Alias for source_fps."""
        return self.source_fps

    def close(self) -> None:
        """Gracefully close and release all stream resources."""
        logger.info("Closing RTSP StreamReader for %s", self.rtsp_url)
        self.disconnect()


# Backward-compatible alias
StreamReader = RTSPReader
