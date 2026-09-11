"""YOLO object detector component wrapping Ultralytics YOLO models."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import cv2
import numpy as np

from app.processing.detection_types import BoundingBox, Detection, FrameDetections

logger = logging.getLogger(__name__)


class YOLODetector:
    """
    Encapsulates Ultralytics YOLO model lifecycle, device resolution, and inference.

    Features:
      - Loads model once at service startup
      - Resolves hardware acceleration (CUDA / Apple Silicon MPS / CPU)
      - Extracts structured Detection objects with class names, bounding boxes, and optional track IDs
      - Supports Ultralytics native tracking (ByteTrack) with persist=True
      - Measures per-frame inference latency
      - Optional headless debug visualization saving annotated frames to disk
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.40,
        iou_threshold: float = 0.50,
        device: str = "auto",
        debug_visualization: bool = False,
        debug_dir: str = "debug_frames",
        tracking_enabled: bool = False,
        tracker_type: str = "bytetrack.yaml",
    ) -> None:
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.device = device
        self.debug_visualization = debug_visualization
        self.debug_dir = debug_dir
        self.tracking_enabled = tracking_enabled
        self.tracker_type = tracker_type

        self.resolved_device = self._resolve_device(device)
        self.model = self._load_model(model_path)

        if self.debug_visualization:
            os.makedirs(self.debug_dir, exist_ok=True)

    @staticmethod
    def _resolve_device(target_device: str) -> str:
        """Automatically select available acceleration hardware."""
        normalized = target_device.strip().lower()

        if normalized != "auto":
            return normalized

        try:
            import torch

            if torch.cuda.is_available():
                selected = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                selected = "mps"
            else:
                selected = "cpu"
        except ImportError:
            selected = "cpu"

        return selected

    def _load_model(self, model_path: str) -> Any:
        """Load YOLO model once into memory."""
        logger.info(
            "Loading YOLO model: %s [Target device: %s -> Resolved: %s]",
            model_path,
            self.device,
            self.resolved_device,
        )
        try:
            from ultralytics import YOLO

            model = YOLO(model_path)
            logger.info("YOLO model '%s' loaded successfully.", model_path)
            return model
        except Exception as exc:
            logger.critical("Failed to load YOLO model from '%s': %s", model_path, exc)
            raise

    def detect(
        self,
        frame: np.ndarray,
        frame_id: int,
        timestamp: float,
    ) -> FrameDetections:
        """
        Execute YOLO inference on a single video frame.

        Args:
            frame: Video frame (numpy BGR image).
            frame_id: Monotonically increasing frame index.
            timestamp: Acquisition timestamp.

        Returns:
            Structured FrameDetections object.
        """
        start_time = time.perf_counter()

        # Run tracking if enabled and supported, otherwise predict
        if self.tracking_enabled and hasattr(self.model, "track"):
            try:
                results = self.model.track(
                    frame,
                    persist=True,
                    tracker=self.tracker_type,
                    conf=self.conf_threshold,
                    iou=self.iou_threshold,
                    device=self.resolved_device,
                    verbose=False,
                )
            except Exception as track_err:
                logger.debug("Ultralytics track fallback to predict: %s", track_err)
                results = self.model.predict(
                    frame,
                    conf=self.conf_threshold,
                    iou=self.iou_threshold,
                    device=self.resolved_device,
                    verbose=False,
                )
        else:
            results = self.model.predict(
                frame,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                device=self.resolved_device,
                verbose=False,
            )

        inference_time_ms = (time.perf_counter() - start_time) * 1000.0

        detections: list[Detection] = []
        if results and len(results) > 0:
            result = results[0]
            boxes = result.boxes

            if boxes is not None and len(boxes) > 0:
                names = result.names or getattr(self.model, "names", {})

                for box in boxes:
                    raw_xyxy = box.xyxy[0]
                    xyxy = raw_xyxy.tolist() if hasattr(raw_xyxy, "tolist") else list(raw_xyxy)
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    cls_name = names.get(cls_id, f"class_{cls_id}")

                    # Extract track_id if available from model.track
                    box_id = getattr(box, "id", None)
                    track_id: int | None = None
                    if box_id is not None:
                        try:
                            track_id = int(box_id[0])
                        except (IndexError, TypeError, ValueError):
                            track_id = None

                    bbox = BoundingBox(
                        x1=round(float(xyxy[0]), 2),
                        y1=round(float(xyxy[1]), 2),
                        x2=round(float(xyxy[2]), 2),
                        y2=round(float(xyxy[3]), 2),
                    )
                    detections.append(
                        Detection(
                            class_id=cls_id,
                            class_name=cls_name,
                            confidence=conf,
                            bbox=bbox,
                            track_id=track_id,
                        )
                    )

            # Optional visual debugging
            if self.debug_visualization:
                try:
                    annotated_frame = result.plot()
                    out_file = os.path.join(self.debug_dir, f"frame_{frame_id:06d}.jpg")
                    cv2.imwrite(out_file, annotated_frame)
                except Exception as viz_err:
                    logger.debug("Failed to write debug frame: %s", viz_err)

        return FrameDetections(
            frame_id=frame_id,
            timestamp=timestamp,
            detections=detections,
            inference_time_ms=inference_time_ms,
            model_name=self.model_path,
        )

    def close(self) -> None:
        """Clean shutdown hook."""
        logger.info("Releasing YOLODetector resources.")
        self.model = None
