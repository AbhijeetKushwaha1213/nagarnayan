"""Ultralytics YOLO detector abstraction for real-time object detection and tracking."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

import numpy as np

from app.detection.schemas import BoundingBox, Detection

logger = logging.getLogger(__name__)


class YOLODetector:
    """
    Encapsulates YOLO model loading, inference execution, and result transformation.

    Features:
      - Configurable model path/weights, confidence threshold, and IoU threshold
      - Configurable CPU/CUDA execution device
      - Robust error handling for corrupt frames or inference exceptions
      - Decoupled from backend APIs and database models
      - Supports Ultralytics ByteTrack integration via track()
      - Mockable model injection for deterministic unit tests
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        device: str = "cpu",
        image_size: int = 640,
        model_instance: Any = None,
    ) -> None:
        self.model_path = model_path
        self.conf_threshold = max(0.01, min(0.99, float(conf_threshold)))
        self.iou_threshold = max(0.01, min(0.99, float(iou_threshold)))
        self.device = str(device).strip().lower()
        self.image_size = int(image_size)

        self._model: Any = model_instance
        self._is_loaded: bool = model_instance is not None

        if self._model is not None:
            logger.info("YOLODetector initialized with injected model instance.")

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def load_model(self) -> bool:
        """
        Load YOLO model weights into memory.

        Returns:
            True if model loaded successfully, False otherwise.
        """
        if self._is_loaded and self._model is not None:
            return True

        logger.info(
            "Loading YOLO model %s on device %s (conf=%.2f, iou=%.2f, imgsz=%d)...",
            self.model_path,
            self.device,
            self.conf_threshold,
            self.iou_threshold,
            self.image_size,
        )

        try:
            from ultralytics import YOLO  # lazy import

            # Ultralytics accepts "cpu", "cuda", "0", "mps", etc.
            self._model = YOLO(self.model_path)
            self._is_loaded = True
            names_count = len(getattr(self._model, "names", {}))
            logger.info(
                "YOLO model %s loaded successfully (%d classes recognized).",
                self.model_path,
                names_count,
            )
            return True

        except Exception as exc:
            logger.error("Failed to load YOLO model %s: %s", self.model_path, exc, exc_info=True)
            self._model = None
            self._is_loaded = False
            return False

    def predict(
        self,
        frame: np.ndarray | None,
        frame_number: int = 0,
        captured_at: datetime | None = None,
        bus_id: str | None = None,
        camera_id: str | None = None,
        stream_id: str | None = None,
        raw_frame_number: int = 0,
    ) -> list[Detection]:
        """
        Run YOLO inference on a single video frame.

        Args:
            frame: NumPy BGR image array.
            frame_number: Monotonically increasing sampled frame index.
            captured_at: Timeframe timestamp of observation.
            bus_id: Optional ID of observing bus.
            camera_id: Optional ID of observing camera.
            stream_id: Optional ID of active stream.
            raw_frame_number: Source frame sequence counter.

        Returns:
            List of structured Detection objects. Never raises exceptions; returns empty list on failure.
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0 or frame.ndim < 2:
            logger.warning("Invalid, None, or empty frame provided to YOLODetector. Skipping inference.")
            return []

        if not self._is_loaded:
            success = self.load_model()
            if not success or self._model is None:
                logger.error("YOLO model is not available. Skipping inference.")
                return []

        ts = captured_at or datetime.now(timezone.utc)

        try:
            results = self._model.predict(
                source=frame,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                device=self.device,
                imgsz=self.image_size,
                verbose=False,
            )
            return self.convert_results_to_detections(
                results=results,
                frame_number=frame_number,
                captured_at=ts,
                bus_id=bus_id,
                camera_id=camera_id,
                stream_id=stream_id,
                raw_frame_number=raw_frame_number,
            )

        except Exception as exc:
            logger.error(
                "Inference failed on frame %d (shape=%s): %s",
                frame_number,
                getattr(frame, "shape", None),
                exc,
                exc_info=False,
            )
            return []

    def track(
        self,
        frame: np.ndarray | None,
        tracker: str = "bytetrack.yaml",
        persist: bool = True,
        frame_number: int = 0,
        captured_at: datetime | None = None,
        bus_id: str | None = None,
        camera_id: str | None = None,
        stream_id: str | None = None,
        raw_frame_number: int = 0,
    ) -> list[Detection]:
        """
        Run YOLO inference with ByteTrack enabled.

        Falls back to predict() if model does not support track() or if track() fails.
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0 or frame.ndim < 2:
            logger.warning("Invalid, None, or empty frame provided to YOLODetector. Skipping tracking.")
            return []

        if not self._is_loaded:
            success = self.load_model()
            if not success or self._model is None:
                logger.error("YOLO model is not available. Skipping tracking.")
                return []

        ts = captured_at or datetime.now(timezone.utc)

        if hasattr(self._model, "track"):
            try:
                results = self._model.track(
                    source=frame,
                    persist=persist,
                    tracker=tracker,
                    conf=self.conf_threshold,
                    iou=self.iou_threshold,
                    device=self.device,
                    imgsz=self.image_size,
                    verbose=False,
                )
                return self.convert_results_to_detections(
                    results=results,
                    frame_number=frame_number,
                    captured_at=ts,
                    bus_id=bus_id,
                    camera_id=camera_id,
                    stream_id=stream_id,
                    raw_frame_number=raw_frame_number,
                )
            except Exception as exc:
                logger.debug("Ultralytics track() failed or unsupported (%s), falling back to predict()", exc)

        return self.predict(
            frame=frame,
            frame_number=frame_number,
            captured_at=ts,
            bus_id=bus_id,
            camera_id=camera_id,
            stream_id=stream_id,
            raw_frame_number=raw_frame_number,
        )

    def convert_results_to_detections(
        self,
        results: Any,
        frame_number: int,
        captured_at: datetime,
        bus_id: str | None = None,
        camera_id: str | None = None,
        stream_id: str | None = None,
        raw_frame_number: int = 0,
    ) -> list[Detection]:
        """
        Parse raw Ultralytics Results object into structured Detection objects.

        Args:
            results: Results output from Ultralytics YOLO predict or track.
        """
        if not results:
            return []

        first_result = results[0] if isinstance(results, (list, tuple)) else results
        boxes = getattr(first_result, "boxes", None)

        if boxes is None or len(boxes) == 0:
            return []

        names = getattr(first_result, "names", {})
        if not names and self._model is not None:
            names = getattr(self._model, "names", {})

        detections: list[Detection] = []

        # Iterate over detected bounding boxes
        for i in range(len(boxes)):
            try:
                box = boxes[i]

                # Extract coordinates (xyxy)
                xyxy_raw = box.xyxy[0] if hasattr(box.xyxy, "__getitem__") else box.xyxy
                if hasattr(xyxy_raw, "tolist"):
                    coords = xyxy_raw.tolist()
                elif hasattr(xyxy_raw, "cpu"):
                    coords = xyxy_raw.cpu().numpy().tolist()
                else:
                    coords = list(xyxy_raw)

                x1, y1, x2, y2 = [float(c) for c in coords[:4]]

                # Extract confidence
                conf_raw = box.conf[0] if hasattr(box.conf, "__getitem__") else box.conf
                conf = float(conf_raw.item() if hasattr(conf_raw, "item") else conf_raw)

                if conf < self.conf_threshold:
                    continue

                # Extract class id and name
                cls_raw = box.cls[0] if hasattr(box.cls, "__getitem__") else box.cls
                class_id = int(cls_raw.item() if hasattr(cls_raw, "item") else cls_raw)
                class_name = str(names.get(class_id, str(class_id)))

                # Extract track_id if assigned by tracker (e.g. Ultralytics ByteTrack)
                track_id: int | None = None
                box_id = getattr(box, "id", None)
                if box_id is not None:
                    try:
                        id_raw = box_id[0] if hasattr(box_id, "__getitem__") else box_id
                        track_id = int(id_raw.item() if hasattr(id_raw, "item") else id_raw)
                    except Exception:
                        track_id = None

                bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)

                det = Detection(
                    class_id=class_id,
                    class_name=class_name,
                    confidence=conf,
                    bounding_box=bbox,
                    frame_number=frame_number,
                    raw_frame_number=raw_frame_number,
                    captured_at=captured_at,
                    track_id=track_id,
                    bus_id=bus_id,
                    camera_id=camera_id,
                    stream_id=stream_id,
                )
                detections.append(det)

            except Exception as parse_err:
                logger.debug("Failed to parse box %d: %s", i, parse_err)
                continue

        return detections
