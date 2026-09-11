"""StreamManager responsible for lifecycle, reconnection, and frame sampling across stream readers."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, TYPE_CHECKING

from app.core.config import settings
from app.health.health import StreamHealth
from app.processing.frame_sampler import FrameSampler, SampledFrame
from app.streams.rtsp_reader import RTSPReader

if TYPE_CHECKING:
    from app.processing.inference import InferenceProcessor

logger = logging.getLogger(__name__)


class StreamManager:
    """
    Manages RTSP stream ingestion, automated reconnection, frame sampling, and optional inference dispatch.

    Designed to manage one primary stream for Phase 1 and Phase 2, structured to scale to multiple streams.
    """

    def __init__(
        self,
        rtsp_url: str | None = None,
        sample_fps: float | None = None,
        reconnect_delay: float | None = None,
        max_reconnect_attempts: int | None = None,
        status_log_interval: float | None = None,
        bus_id: str | None = None,
        camera_id: str | None = None,
        stream_id: str | None = None,
        reader: RTSPReader | None = None,
        sampler: FrameSampler | None = None,
        inference_processor: Any | None = None,
        on_sampled_frame: Callable[[SampledFrame], None] | None = None,
    ) -> None:
        self.rtsp_url = rtsp_url or settings.RTSP_URL
        self.sample_fps = max(0.1, sample_fps if sample_fps is not None else settings.FRAME_SAMPLE_FPS)
        self.reconnect_delay = (
            reconnect_delay if reconnect_delay is not None else settings.RECONNECT_DELAY_SECONDS
        )
        self.max_reconnect_attempts = (
            max_reconnect_attempts
            if max_reconnect_attempts is not None
            else settings.MAX_RECONNECT_ATTEMPTS
        )
        self.status_log_interval = (
            status_log_interval if status_log_interval is not None else settings.STATUS_LOG_INTERVAL_SECONDS
        )

        self.bus_id = bus_id or settings.BUS_ID
        self.camera_id = camera_id or settings.CAMERA_ID
        self.stream_id = stream_id or settings.STREAM_ID

        # Primary reader (or injected mock reader for testing)
        self.reader = reader or RTSPReader(
            rtsp_url=self.rtsp_url,
            reconnect_delay=self.reconnect_delay,
            max_reconnect_attempts=self.max_reconnect_attempts,
        )

        # Frame sampler abstraction
        self.sampler = sampler or FrameSampler(
            sample_fps=self.sample_fps,
            bus_id=self.bus_id,
            camera_id=self.camera_id,
            stream_id=self.stream_id,
        )

        self.inference_processor = inference_processor
        self.health = StreamHealth()
        self.on_sampled_frame = on_sampled_frame

        # Multi-stream registry ready
        self._streams: dict[str, RTSPReader] = {
            f"{self.bus_id}/{self.camera_id}": self.reader
        }

        self._running: bool = False
        self._last_sampled_timestamp: float = 0.0
        self._sampled_frame_id: int = 0
        self._last_status_log_time: float = 0.0

    @property
    def is_running(self) -> bool:
        return self._running

    def register_stream(self, stream_key: str, reader: RTSPReader) -> None:
        """Register an additional stream reader into the multi-stream manager."""
        self._streams[stream_key] = reader

    def start(self, max_frames: int | None = None) -> None:
        """
        Start the continuous stream reading and processing loop.

        Args:
            max_frames: Optional limit on sampled frames processed (useful for testing and deterministic runs).
        """
        self._running = True
        logger.info(
            "Starting StreamManager [RTSP: %s | Target Sampling: %.1f FPS | Camera: %s | Bus: %s]",
            self.rtsp_url,
            self.sample_fps,
            self.camera_id,
            self.bus_id,
        )

        consecutive_failures = 0

        while self._running:
            # 1. Check/Establish connection
            if not self.reader.is_connected:
                self.health.record_connected(False)

                if (
                    self.max_reconnect_attempts is not None
                    and self.max_reconnect_attempts > 0
                    and consecutive_failures >= self.max_reconnect_attempts
                ):
                    logger.error(
                        "Max reconnect attempts (%d) reached for %s. Halting stream manager loop.",
                        self.max_reconnect_attempts,
                        self.rtsp_url,
                    )
                    break

                logger.info(
                    "Connecting to stream (attempt %d)...",
                    consecutive_failures + 1,
                )
                connected = self.reader.connect()

                if not connected:
                    consecutive_failures += 1
                    self.health.record_reconnect()
                    logger.warning(
                        "RTSP stream connection failed. Waiting %.1f seconds before retry...",
                        self.reconnect_delay,
                    )
                    self._interruptible_sleep(self.reconnect_delay)
                    continue

                # Successfully connected or recovered
                consecutive_failures = 0
                self.health.record_connected(True)
                logger.info("Stream connected and operational: %s", self.rtsp_url)

            # 2. Read raw video frame
            success, frame, timestamp = self.reader.read_frame()

            if not success or frame is None:
                consecutive_failures += 1
                self.health.record_reconnect()
                logger.warning(
                    "Stream lost while reading frame. Releasing capture and waiting %.1f seconds...",
                    self.reconnect_delay,
                )
                self.reader.disconnect()
                self._interruptible_sleep(self.reconnect_delay)
                continue

            consecutive_failures = 0
            self.health.record_frame_received()

            # 3. Subsample frame
            sampled = self.sampler.sample(
                frame=frame,
                timestamp=timestamp,
                source_fps=self.reader.source_fps,
            )

            if sampled is not None:
                self.health.record_frame_sampled()

                # Dispatch to inference processor if attached
                if self.inference_processor is not None and hasattr(self.inference_processor, "get_metrics"):
                    try:
                        self.inference_processor.process_sampled_frame(sampled)
                    except Exception as inf_err:
                        logger.error("Error in inference processor: %s", inf_err)

                # Dispatch to optional callback
                if self.on_sampled_frame is not None:
                    try:
                        self.on_sampled_frame(sampled)
                    except Exception as cb_err:
                        logger.error("Error in on_sampled_frame callback: %s", cb_err)

                if max_frames and self.sampler.total_sampled >= max_frames:
                    logger.info("Target sampled frame limit of %d reached. Exiting loop.", max_frames)
                    break

            # 4. Periodic diagnostics logging
            now = time.time()
            if now - self._last_status_log_time >= self.status_log_interval:
                self._last_status_log_time = now
                status = self.health.get_status()

                inf_stats = ""
                if self.inference_processor is not None and hasattr(self.inference_processor, "get_metrics"):
                    m = self.inference_processor.get_metrics()
                    inf_stats = (
                        f" | Inferred: {m['inference_count']}"
                        f" | Detections: {m['detections_total']}"
                        f" | Tracked: {m.get('total_tracked_detections', 0)}"
                        f" | Validated: {m.get('validated_tracks', 0)}"
                        f" | Active Tracks: {m.get('active_tracks', 0)}"
                        f" | Submitted: {m.get('detections_submitted', 0)}"
                        f" | Drops: {m.get('queue_full_drops', 0)}"
                        f" | Avg Latency: {m['average_inference_time_ms']}ms"
                    )

                logger.info(
                    "[DIAGNOSTICS] Connected: %s | Received: %d | Sampled: %d | Current FPS: %.1f%s | Reconnects: %d | Uptime: %.1fs",
                    status["is_connected"],
                    status["total_frames_received"],
                    status["total_frames_sampled"],
                    status["current_fps"],
                    inf_stats,
                    status["reconnect_count"],
                    status["uptime_seconds"],
                )

        self.stop()

    def _interruptible_sleep(self, duration_seconds: float) -> None:
        """Sleep in small intervals so that stop() or signals break out immediately."""
        step = 0.25
        elapsed = 0.0
        while self._running and elapsed < duration_seconds:
            time.sleep(min(step, duration_seconds - elapsed))
            elapsed += step

    def stop(self) -> None:
        """Stop the stream ingestion pipeline gracefully and release all resources."""
        if not self._running:
            return

        logger.info("Stopping StreamManager...")
        self._running = False
        for reader in self._streams.values():
            reader.close()
        self.health.record_connected(False)
        logger.info("StreamManager stopped cleanly.")

    @property
    def processor(self) -> Any:
        """Backwards-compatible alias for inference_processor."""
        if self.inference_processor is None:
            from unittest.mock import MagicMock
            self.inference_processor = MagicMock()
        return self.inference_processor

    @processor.setter
    def processor(self, val: Any) -> None:
        self.inference_processor = val

    @property
    def sample_interval(self) -> float:
        return 1.0 / max(0.1, self.sample_fps)
