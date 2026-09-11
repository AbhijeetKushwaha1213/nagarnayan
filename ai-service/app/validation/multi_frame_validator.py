"""Multi-frame temporal observation validator over a configurable sliding window."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any

from app.detection.schemas import BoundingBox, TrackedDetection, ValidatedDetection
from app.detection.tracker import Track

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrackObservation:
    """Historical observation of a tracked object in a specific frame."""

    frame_number: int
    confidence: float
    bbox: BoundingBox
    timestamp: datetime


class MultiFrameValidator:
    """
    Validates tracked detections across multiple consecutive frames within a sliding window.

    Distinction:
      - Detection confidence != Validation status.
      - A high-confidence detection (e.g. 0.90) is unvalidated if seen only once.
      - Validation requires temporal consistency: at least min_frames within window_frames,
        and an average confidence >= min_confidence.
    """

    def __init__(
        self,
        min_frames: int = 3,
        window_frames: int = 5,
        min_confidence: float = 0.30,
    ) -> None:
        self.min_frames = max(1, int(min_frames))
        self.window_frames = max(self.min_frames, int(window_frames))
        self.min_confidence = max(0.01, min(0.99, float(min_confidence)))

        # Maps track_id -> bounded deque of recent observations
        self.track_history: dict[int, deque[TrackObservation]] = {}
        self.validated_track_ids: set[int] = set()
        self.validation_rejections: int = 0

    @property
    def validated_tracks_count(self) -> int:
        """Total unique tracks that have met validation criteria."""
        return len(self.validated_track_ids)

    def validate(
        self,
        tracked_detections: list[TrackedDetection],
        active_tracks: dict[int, Track],
        frame_number: int,
        timestamp: datetime | None = None,
    ) -> list[ValidatedDetection]:
        """
        Evaluate tracked detections and return temporally validated detection candidates.

        Args:
            tracked_detections: Detections with persistent track_ids from current frame.
            active_tracks: Active track dictionary from ObjectTracker.
            frame_number: Monotonically increasing sampled frame index.
            timestamp: Acquisition timestamp.

        Returns:
            List of ValidatedDetection objects that satisfied multi-frame criteria.
        """
        ts = timestamp or datetime.now(timezone.utc)
        validated_results: list[ValidatedDetection] = []

        # Step 1: Evict history for tracks that are no longer active in the tracker
        active_ids = set(active_tracks.keys())
        stale_ids = [tid for tid in self.track_history if tid not in active_ids]
        for tid in stale_ids:
            del self.track_history[tid]

        # Step 2: Ingest current frame observations and test validation criteria
        for td in tracked_detections:
            tid = td.track_id
            if tid not in self.track_history:
                self.track_history[tid] = deque(maxlen=self.window_frames)

            obs = TrackObservation(
                frame_number=frame_number,
                confidence=td.confidence,
                bbox=td.bounding_box,
                timestamp=ts,
            )
            history = self.track_history[tid]
            history.append(obs)

            # Evict observations that fall outside the sliding frame window
            min_valid_frame = frame_number - self.window_frames + 1
            while history and history[0].frame_number < min_valid_frame:
                history.popleft()

            frames_in_window = len(history)
            avg_confidence = sum(o.confidence for o in history) / frames_in_window

            # Track lifecycle metadata from tracker
            track_meta = active_tracks.get(tid)
            first_seen = track_meta.first_seen_frame if track_meta else frame_number
            last_seen = track_meta.last_seen_frame if track_meta else frame_number
            total_obs = track_meta.observation_count if track_meta else frames_in_window
            max_conf = track_meta.max_confidence if track_meta else td.confidence
            last_seen_ts = track_meta.last_seen_timestamp if track_meta else ts

            # Temporal persistence and confidence validation check
            is_persisted = frames_in_window >= self.min_frames
            is_confident = avg_confidence >= self.min_confidence

            if is_persisted and is_confident:
                if track_meta is not None:
                    track_meta.validated = True
                self.validated_track_ids.add(tid)

                validated_results.append(
                    ValidatedDetection(
                        tracked_detection=td,
                        track_id=tid,
                        class_id=td.class_id,
                        class_name=td.class_name,
                        confidence=td.confidence,
                        bounding_box=td.bounding_box,
                        frame_number=frame_number,
                        raw_frame_number=td.raw_frame_number,
                        captured_at=td.captured_at,
                        first_seen_frame=first_seen,
                        last_seen_frame=last_seen,
                        observation_count=total_obs,
                        max_confidence=max_conf,
                        average_confidence=round(avg_confidence, 4),
                        validated=True,
                        last_seen_timestamp=last_seen_ts,
                        bus_id=td.bus_id,
                        camera_id=td.camera_id,
                        stream_id=td.stream_id,
                        extra=td.extra,
                    )
                )
            else:
                self.validation_rejections += 1
                logger.debug(
                    "Track %d unvalidated at frame %d: obs_in_window=%d/%d, avg_conf=%.2f/%.2f",
                    tid,
                    frame_number,
                    frames_in_window,
                    self.min_frames,
                    avg_confidence,
                    self.min_confidence,
                )

        return validated_results

    def reset(self) -> None:
        """Reset validator history and statistics."""
        self.track_history.clear()
        self.validated_track_ids.clear()
        self.validation_rejections = 0

    def get_metrics(self) -> dict[str, int]:
        """Return validation telemetry statistics."""
        return {
            "validated_tracks": len(self.validated_track_ids),
            "validation_rejections": self.validation_rejections,
        }
