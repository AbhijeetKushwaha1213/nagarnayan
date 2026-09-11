"""Multi-frame observation validation over a bounded sliding window."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import logging

from app.processing.detection_types import BoundingBox, TrackedDetection, ValidatedDetection
from app.processing.tracker import Track

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrackObservation:
    """Historical observation of a tracked object in a specific frame."""

    frame_id: int
    confidence: float
    bbox: BoundingBox
    timestamp: float


class MultiFrameValidator:
    """
    Validates tracked detections across multiple consecutive frames.

    Prevents transient false positives from immediately triggering municipal events.
    Enforces:
      - Temporal persistence: Object must be observed in at least min_frames within window_frames.
      - Mean confidence threshold: Average confidence over the window must meet min_confidence.
    """

    def __init__(
        self,
        min_frames: int = 3,
        window_frames: int = 5,
        min_confidence: float = 0.40,
    ) -> None:
        self.min_frames = min_frames
        self.window_frames = window_frames
        self.min_confidence = min_confidence

        # Maps track_id -> bounded deque of recent TrackObservations
        self.track_history: dict[int, deque[TrackObservation]] = {}

    def validate(
        self,
        tracked_detections: list[TrackedDetection],
        active_tracks: dict[int, Track],
        frame_id: int,
        timestamp: float,
    ) -> list[ValidatedDetection]:
        """
        Evaluate tracked detections and return validated urban observations.

        Args:
            tracked_detections: List of tracked detections for the current frame.
            active_tracks: Mapping of active Track state objects from ObjectTracker.
            frame_id: Monotonically increasing frame index.
            timestamp: Acquisition timestamp.

        Returns:
            List of ValidatedDetection objects that satisfied multi-frame criteria.
        """
        validated_results: list[ValidatedDetection] = []

        # Step 1: Evict history for tracks that have been expired from active tracks
        active_ids = set(active_tracks.keys())
        stale_ids = [tid for tid in self.track_history if tid not in active_ids]
        for tid in stale_ids:
            del self.track_history[tid]

        # Step 2: Ingest current frame observations and test validation conditions
        for td in tracked_detections:
            if td.track_id not in self.track_history:
                self.track_history[td.track_id] = deque(maxlen=self.window_frames)

            obs = TrackObservation(
                frame_id=frame_id,
                confidence=td.confidence,
                bbox=td.bbox,
                timestamp=timestamp,
            )
            self.track_history[td.track_id].append(obs)

            history = self.track_history[td.track_id]
            frames_in_window = len(history)
            avg_confidence = sum(o.confidence for o in history) / frames_in_window

            # Metadata from active track
            track_meta = active_tracks.get(td.track_id)
            total_frames_seen = track_meta.frames_seen if track_meta else frames_in_window
            first_seen = track_meta.first_seen_timestamp if track_meta else timestamp
            last_seen = track_meta.last_seen_timestamp if track_meta else timestamp

            # Validation criteria check
            if frames_in_window >= self.min_frames and avg_confidence >= self.min_confidence:
                validated_results.append(
                    ValidatedDetection(
                        track_id=td.track_id,
                        class_id=td.class_id,
                        class_name=td.class_name,
                        confidence=td.confidence,
                        average_confidence=round(avg_confidence, 4),
                        bbox=td.bbox,
                        frame_id=frame_id,
                        timestamp=timestamp,
                        frames_seen=total_frames_seen,
                        first_seen_timestamp=first_seen,
                        last_seen_timestamp=last_seen,
                        validation_status="validated",
                    )
                )

        return validated_results

    def reset(self) -> None:
        """Clear validation history."""
        self.track_history.clear()
