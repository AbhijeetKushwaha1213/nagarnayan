"""Object tracking component maintaining persistent track identities across video frames."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any

from app.detection.schemas import BoundingBox, Detection, TrackedDetection

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """
    Maintains persistent state and lifecycle statistics for a tracked physical object.
    """

    track_id: int
    class_id: int
    class_name: str
    first_seen_frame: int
    last_seen_frame: int
    observation_count: int
    max_confidence: float
    total_confidence: float
    last_seen_timestamp: datetime
    last_bbox: BoundingBox
    validated: bool = False
    frames_unseen: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def average_confidence(self) -> float:
        """Mean confidence score across all observations of this track."""
        if self.observation_count == 0:
            return 0.0
        return round(float(self.total_confidence / self.observation_count), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "first_seen_frame": self.first_seen_frame,
            "last_seen_frame": self.last_seen_frame,
            "observation_count": self.observation_count,
            "max_confidence": round(float(self.max_confidence), 4),
            "average_confidence": self.average_confidence,
            "validated": self.validated,
            "frames_unseen": self.frames_unseen,
            "last_seen_timestamp": self.last_seen_timestamp.isoformat(),
            "last_bbox": self.last_bbox.to_dict(),
            "extra": self.extra,
        }


class ObjectTracker:
    """
    Maintains persistent track IDs and lifecycle states for detected objects across frames.

    Capabilities:
      - Ingests persistent track IDs from Ultralytics ByteTrack whenever available.
      - Implements spatial IoU-based association fallback for mock detectors and frames without native IDs.
      - Tracks temporal lifecycle (first_seen_frame, last_seen_frame, observation_count, confidences).
      - Handles temporary missed detections gracefully (tolerates up to max_age unobserved frames).
      - Prunes stale/expired tracks once they exceed max_age unobserved frames.
      - Maintains telemetry on active tracks, total tracks created, and tracked detections.
    """

    def __init__(
        self,
        enabled: bool = True,
        tracker_type: str = "bytetrack.yaml",
        iou_threshold: float = 0.50,
        max_age: int = 30,
    ) -> None:
        self.enabled = bool(enabled)
        self.tracker_type = str(tracker_type)
        self.iou_threshold = max(0.01, min(1.0, float(iou_threshold)))
        self.max_age = max(1, int(max_age))

        self.active_tracks: dict[int, Track] = {}
        self._next_track_id: int = 1

        # Telemetry metrics
        self.total_tracks_created: int = 0
        self.total_tracked_detections: int = 0

    @property
    def active_track_count(self) -> int:
        """Total number of currently tracked active objects."""
        return len(self.active_tracks)

    def update(
        self,
        detections: list[Detection],
        frame_number: int,
        captured_at: datetime | None = None,
    ) -> list[TrackedDetection]:
        """
        Update tracking state with new detections from the current frame.

        Args:
            detections: List of raw YOLO detections from the current frame.
            frame_number: Monotonically increasing sampled frame index.
            captured_at: Acquisition timestamp.

        Returns:
            List of TrackedDetection objects carrying persistent track_id.
        """
        ts = captured_at or datetime.now(timezone.utc)

        if not self.enabled:
            # Fallback when tracking is disabled
            results: list[TrackedDetection] = []
            for idx, d in enumerate(detections, start=1):
                tid = d.track_id if d.track_id is not None else idx
                results.append(
                    TrackedDetection(
                        class_id=d.class_id,
                        class_name=d.class_name,
                        confidence=d.confidence,
                        bounding_box=d.bounding_box,
                        track_id=tid,
                        frame_number=frame_number,
                        raw_frame_number=d.raw_frame_number,
                        captured_at=ts,
                        bus_id=d.bus_id,
                        camera_id=d.camera_id,
                        stream_id=d.stream_id,
                        extra=d.extra,
                    )
                )
            self.total_tracked_detections += len(results)
            return results

        tracked_results: list[TrackedDetection] = []
        unmatched_detections: list[Detection] = []
        matched_track_ids: set[int] = set()

        # Step 1: Process detections that already carry a native track_id (e.g. from ByteTrack)
        for det in detections:
            if det.track_id is not None and det.track_id > 0:
                tid = det.track_id
                matched_track_ids.add(tid)

                if tid in self.active_tracks:
                    trk = self.active_tracks[tid]
                    trk.last_bbox = det.bounding_box
                    trk.last_seen_frame = frame_number
                    trk.last_seen_timestamp = ts
                    trk.observation_count += 1
                    trk.max_confidence = max(trk.max_confidence, det.confidence)
                    trk.total_confidence += det.confidence
                    trk.frames_unseen = 0
                else:
                    trk = Track(
                        track_id=tid,
                        class_id=det.class_id,
                        class_name=det.class_name,
                        first_seen_frame=frame_number,
                        last_seen_frame=frame_number,
                        observation_count=1,
                        max_confidence=det.confidence,
                        total_confidence=det.confidence,
                        last_seen_timestamp=ts,
                        last_bbox=det.bounding_box,
                    )
                    self.active_tracks[tid] = trk
                    self.total_tracks_created += 1
                    if tid >= self._next_track_id:
                        self._next_track_id = tid + 1

                tracked_results.append(
                    TrackedDetection(
                        class_id=det.class_id,
                        class_name=det.class_name,
                        confidence=det.confidence,
                        bounding_box=det.bounding_box,
                        track_id=tid,
                        frame_number=frame_number,
                        raw_frame_number=det.raw_frame_number,
                        captured_at=ts,
                        bus_id=det.bus_id,
                        camera_id=det.camera_id,
                        stream_id=det.stream_id,
                        extra=det.extra,
                    )
                )
            else:
                unmatched_detections.append(det)

        # Step 2: Spatial IoU matching fallback for detections without an assigned track_id
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

                    iou_score = det.bounding_box.iou(candidate.last_bbox)
                    if iou_score >= self.iou_threshold and iou_score > best_iou:
                        best_iou = iou_score
                        best_track = candidate

                if best_track is not None:
                    tid = best_track.track_id
                    matched_track_ids.add(tid)
                    best_track.last_bbox = det.bounding_box
                    best_track.last_seen_frame = frame_number
                    best_track.last_seen_timestamp = ts
                    best_track.observation_count += 1
                    best_track.max_confidence = max(best_track.max_confidence, det.confidence)
                    best_track.total_confidence += det.confidence
                    best_track.frames_unseen = 0

                    tracked_results.append(
                        TrackedDetection(
                            class_id=det.class_id,
                            class_name=det.class_name,
                            confidence=det.confidence,
                            bounding_box=det.bounding_box,
                            track_id=tid,
                            frame_number=frame_number,
                            raw_frame_number=det.raw_frame_number,
                            captured_at=ts,
                            bus_id=det.bus_id,
                            camera_id=det.camera_id,
                            stream_id=det.stream_id,
                            extra=det.extra,
                        )
                    )
                else:
                    # New object entering observation area
                    new_id = self._next_track_id
                    self._next_track_id += 1
                    new_track = Track(
                        track_id=new_id,
                        class_id=det.class_id,
                        class_name=det.class_name,
                        first_seen_frame=frame_number,
                        last_seen_frame=frame_number,
                        observation_count=1,
                        max_confidence=det.confidence,
                        total_confidence=det.confidence,
                        last_seen_timestamp=ts,
                        last_bbox=det.bounding_box,
                    )
                    self.active_tracks[new_id] = new_track
                    self.total_tracks_created += 1
                    matched_track_ids.add(new_id)

                    tracked_results.append(
                        TrackedDetection(
                            class_id=det.class_id,
                            class_name=det.class_name,
                            confidence=det.confidence,
                            bounding_box=det.bounding_box,
                            track_id=new_id,
                            frame_number=frame_number,
                            raw_frame_number=det.raw_frame_number,
                            captured_at=ts,
                            bus_id=det.bus_id,
                            camera_id=det.camera_id,
                            stream_id=det.stream_id,
                            extra=det.extra,
                        )
                    )

        # Step 3: Update unseen counts and prune expired/stale tracks
        expired_track_ids: list[int] = []
        for tid, trk in self.active_tracks.items():
            if tid not in matched_track_ids:
                trk.frames_unseen = frame_number - trk.last_seen_frame
                if trk.frames_unseen > self.max_age:
                    expired_track_ids.append(tid)

        for tid in expired_track_ids:
            logger.debug(
                "Track %d (%s) expired after %d unseen frames. Pruning from active tracks.",
                tid,
                self.active_tracks[tid].class_name,
                self.active_tracks[tid].frames_unseen,
            )
            del self.active_tracks[tid]

        self.total_tracked_detections += len(tracked_results)
        return tracked_results

    def reset(self) -> None:
        """Reset tracker state and active tracks."""
        self.active_tracks.clear()
        self._next_track_id = 1
        self.total_tracks_created = 0
        self.total_tracked_detections = 0

    def get_metrics(self) -> dict[str, int]:
        """Return current tracker telemetry counters."""
        return {
            "active_tracks": len(self.active_tracks),
            "total_tracks_created": self.total_tracks_created,
            "total_tracked_detections": self.total_tracked_detections,
        }
