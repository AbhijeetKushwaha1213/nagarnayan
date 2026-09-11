"""Multi-object tracking component maintaining persistent tracks across video frames."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from app.processing.detection_types import BoundingBox, Detection, TrackedDetection

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """State of an active tracked object across consecutive frames."""

    track_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    first_seen_timestamp: float
    last_seen_timestamp: float
    frames_seen: int
    last_frame_id: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox.to_dict(),
            "first_seen_timestamp": self.first_seen_timestamp,
            "last_seen_timestamp": self.last_seen_timestamp,
            "frames_seen": self.frames_seen,
            "last_frame_id": self.last_frame_id,
        }


class ObjectTracker:
    """
    Maintains persistent track IDs and lifecycle states for detected objects.

    Supports:
      - Direct ingestion of tracker IDs produced by Ultralytics ByteTrack.
      - Spatial IoU-based association fallback for mock detectors or raw models.
      - Track lifetime management (first_seen, last_seen, frames_seen).
      - Time-to-live (TTL) expiration after TRACK_MAX_AGE unobserved frames.
    """

    def __init__(
        self,
        enabled: bool = True,
        iou_threshold: float = 0.50,
        max_age: int = 30,
    ) -> None:
        self.enabled = enabled
        self.iou_threshold = iou_threshold
        self.max_age = max_age

        self.active_tracks: dict[int, Track] = {}
        self._next_track_id: int = 1

    @property
    def active_track_count(self) -> int:
        """Total number of currently tracked active objects."""
        return len(self.active_tracks)

    def update(
        self,
        detections: list[Detection],
        frame_id: int,
        timestamp: float,
    ) -> list[TrackedDetection]:
        """
        Update tracking state with new detections from the current frame.

        Args:
            detections: List of raw YOLO detections.
            frame_id: Monotonically increasing frame index.
            timestamp: Acquisition timestamp of the frame.

        Returns:
            List of TrackedDetection objects for the current frame.
        """
        if not self.enabled:
            return [
                TrackedDetection(
                    track_id=d.track_id if d.track_id is not None else idx,
                    class_id=d.class_id,
                    class_name=d.class_name,
                    confidence=d.confidence,
                    bbox=d.bbox,
                    frame_id=frame_id,
                    timestamp=timestamp,
                )
                for idx, d in enumerate(detections, start=1)
            ]

        tracked_results: list[TrackedDetection] = []
        unmatched_detections: list[Detection] = []
        matched_track_ids: set[int] = set()

        # Step 1: Match detections that already contain a tracker ID (e.g. from Ultralytics)
        for det in detections:
            if det.track_id is not None:
                tid = det.track_id
                matched_track_ids.add(tid)
                if tid in self.active_tracks:
                    trk = self.active_tracks[tid]
                    trk.bbox = det.bbox
                    trk.confidence = det.confidence
                    trk.last_seen_timestamp = timestamp
                    trk.frames_seen += 1
                    trk.last_frame_id = frame_id
                else:
                    trk = Track(
                        track_id=tid,
                        class_id=det.class_id,
                        class_name=det.class_name,
                        confidence=det.confidence,
                        bbox=det.bbox,
                        first_seen_timestamp=timestamp,
                        last_seen_timestamp=timestamp,
                        frames_seen=1,
                        last_frame_id=frame_id,
                    )
                    self.active_tracks[tid] = trk
                    if tid >= self._next_track_id:
                        self._next_track_id = tid + 1

                tracked_results.append(
                    TrackedDetection(
                        track_id=trk.track_id,
                        class_id=trk.class_id,
                        class_name=trk.class_name,
                        confidence=trk.confidence,
                        bbox=trk.bbox,
                        frame_id=frame_id,
                        timestamp=timestamp,
                    )
                )
            else:
                unmatched_detections.append(det)

        # Step 2: Fallback IoU spatial matching for detections without a track_id
        if unmatched_detections:
            available_tracks = [
                t for t in self.active_tracks.values()
                if t.track_id not in matched_track_ids
            ]

            for det in unmatched_detections:
                best_track: Track | None = None
                best_iou = 0.0

                for candidate in available_tracks:
                    if candidate.track_id in matched_track_ids:
                        continue
                    if candidate.class_id != det.class_id:
                        continue

                    iou_score = det.bbox.iou(candidate.bbox)
                    if iou_score >= self.iou_threshold and iou_score > best_iou:
                        best_iou = iou_score
                        best_track = candidate

                if best_track is not None:
                    matched_track_ids.add(best_track.track_id)
                    best_track.bbox = det.bbox
                    best_track.confidence = det.confidence
                    best_track.last_seen_timestamp = timestamp
                    best_track.frames_seen += 1
                    best_track.last_frame_id = frame_id

                    tracked_results.append(
                        TrackedDetection(
                            track_id=best_track.track_id,
                            class_id=best_track.class_id,
                            class_name=best_track.class_name,
                            confidence=best_track.confidence,
                            bbox=best_track.bbox,
                            frame_id=frame_id,
                            timestamp=timestamp,
                        )
                    )
                else:
                    new_id = self._next_track_id
                    self._next_track_id += 1
                    new_track = Track(
                        track_id=new_id,
                        class_id=det.class_id,
                        class_name=det.class_name,
                        confidence=det.confidence,
                        bbox=det.bbox,
                        first_seen_timestamp=timestamp,
                        last_seen_timestamp=timestamp,
                        frames_seen=1,
                        last_frame_id=frame_id,
                    )
                    self.active_tracks[new_id] = new_track
                    matched_track_ids.add(new_id)

                    tracked_results.append(
                        TrackedDetection(
                            track_id=new_track.track_id,
                            class_id=new_track.class_id,
                            class_name=new_track.class_name,
                            confidence=new_track.confidence,
                            bbox=new_track.bbox,
                            frame_id=frame_id,
                            timestamp=timestamp,
                        )
                    )

        # Step 3: Prune tracks that have not been observed in > max_age frames
        expired_ids = [
            tid for tid, trk in self.active_tracks.items()
            if frame_id - trk.last_frame_id > self.max_age
        ]
        for tid in expired_ids:
            del self.active_tracks[tid]

        return tracked_results

    def reset(self) -> None:
        """Reset internal tracking state."""
        self.active_tracks.clear()
        self._next_track_id = 1
