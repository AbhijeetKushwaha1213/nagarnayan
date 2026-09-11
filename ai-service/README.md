# Nagar Nayan — AI Video Intelligence Service

## Phase 4: Validated Detection → Backend Ingestion

The **AI Video Intelligence Service** consumes live RTSP video feeds from bus-mounted cameras, performs deterministic frame sampling, runs real-time YOLO object detection, maintains persistent tracking identities with ByteTrack / spatial IoU association, validates observations across multi-frame sliding windows, and transmits validated detection metadata to the Nagar Nayan FastAPI backend.

---

## Pipeline Architecture

```
Physical Bus Camera
       ↓
Video Stream Server (FFmpeg + MediaMTX)
       ↓ RTSP (e.g. rtsp://localhost:8554/bus/front)
┌─────────────────────────────────────────────────────────────┐
│ AI Video Intelligence Service (ai-service/)                 │
│   ├── OpenCV VideoCapture (TCP transport)                   │
│   ├── RTSPReader (low-latency, auto-reconnect)              │
│   ├── FrameSampler (downsamples e.g. 25/30 FPS → 5 FPS)      │
│   ├── In-Memory Frame Metadata (SampledFrame)               │
│   ├── YOLODetector (Ultralytics YOLO, CPU/CUDA flexible)    │
│   │     ↓ [Raw Detections]                                  │
│   ├── ObjectTracker (ByteTrack / IoU fallback)              │
│   │     ↓ [Tracked Detections with Persistent track_id]     │
│   ├── MultiFrameValidator (Temporal Persistence Filter)     │
│   │     ↓ [Validated Detection Objects ONLY]                │
│   ├── DetectionSender (Bounded Queue, Non-blocking Enqueue) │
│   │     ↓ [BackendDetectionPayload]                         │
│   ├── BackendClient (httpx.AsyncClient + Bounded Retries)   │
│   └── StreamManager (lifecycle & diagnostics)              │
└─────────────────────────────────────────────────────────────┘
       ↓ HTTP POST /api/v1/detections (FastAPI DetectionCreate)
Nagar Nayan Backend (FastAPI + PostgreSQL/PostGIS)
       ↓
Event Correlation & Municipal Alert Engine
```

### Strict Architectural Boundaries
1. **Send ONLY Validated Detections**: Raw YOLO detections, single-frame noise, and unvalidated tracks are **never** transmitted to the backend.
2. **Zero Fabricated GPS**: When GPS is unavailable, `latitude` and `longitude` are strictly `None` / `null`. Fake coordinates are never manufactured.
3. **Deterministic Frame Reference**: Formatted as `<stream_id or camera_id>:<raw_frame_number>:<track_id>:<detection_type>` to ensure backend idempotency and deduplication function correctly.
4. **Non-blocking Video Pipeline**: Transmission uses a bounded worker queue (`max_queue_size=100`). If congested, newest detections are dropped with logged warnings, ensuring the OpenCV frame capture loop never freezes.
5. **No Direct DB Access**: The AI service communicates exclusively via the documented HTTP REST API contract (`POST /api/v1/detections`). It does not connect to PostgreSQL.
6. **No Urban Event / Alert Creation**: Event correlation and alerting belong strictly to the backend.

---

## Backend Ingestion Contract

Validated detections are mapped to the FastAPI backend schema (`DetectionCreate`):

```json
{
  "bus_id": "00000000-0000-0000-0000-000000000001",
  "camera_id": "00000000-0000-0000-0000-000000000001",
  "stream_id": null,
  "detection_type": "VEHICLE",
  "confidence": 0.885,
  "latitude": null,
  "longitude": null,
  "detected_at": "2026-09-10T12:00:00.000Z",
  "frame_reference": "00000000-0000-0000-0000-000000000001:150:42:VEHICLE",
  "metadata": {
    "track_id": 42,
    "class_name": "car",
    "class_id": 2,
    "first_seen_frame": 1,
    "last_seen_frame": 5,
    "observation_count": 4,
    "max_confidence": 0.92,
    "average_confidence": 0.885,
    "bounding_box": { "x1": 100.0, "y1": 150.0, "x2": 300.0, "y2": 400.0 }
  }
}
```

### Detection Type Mapping
- `car`, `truck`, `bus`, `motorcycle`, `bicycle` → `VEHICLE`
- `person`, `pedestrian` → `PEDESTRIAN`
- `pothole` → `POTHOLE`
- `damaged_road` → `DAMAGED_ROAD`
- `waterlogging` → `WATERLOGGING`
- Unmapped COCO classes (e.g. `chair`, `kite`, `sports ball`) are logged and skipped.

---

## Configuration

Configuration is loaded from environment variables or YAML files using Pydantic Settings.

| Variable | Type | Default | Description |
|---|---|---|---|
| `RTSP_URL` | str | `rtsp://localhost:8554/bus/front` | RTSP stream endpoint |
| `FRAME_SAMPLE_FPS` | float | `5.0` | Sampling rate from source video |
| `BUS_ID` | UUID | `00000000-0000-0000-0000-000000000001` | Identifier of the transit bus |
| `CAMERA_ID` | UUID | `00000000-0000-0000-0000-000000000001` | Identifier of the camera |
| `STREAM_ID` | UUID / null | `null` | Optional stream session UUID |
| `YOLO_MODEL` | str | `yolov8n.pt` | Ultralytics model path or weights |
| `YOLO_CONFIDENCE_THRESHOLD` | float | `0.25` | Minimum raw detection confidence |
| `YOLO_IOU_THRESHOLD` | float | `0.45` | NMS IoU threshold |
| `YOLO_DEVICE` | str | `cpu` | Inference hardware target (`cpu`, `cuda`, `mps`, `auto`) |
| `TRACKING_ENABLED` | bool | `true` | Maintain persistent track IDs across frames |
| `TRACKER_TYPE` | str | `bytetrack.yaml` | Tracker algorithm configuration |
| `VALIDATION_MIN_FRAMES` | int | `3` | Minimum observations required to validate |
| `VALIDATION_WINDOW_FRAMES` | int | `5` | Sliding window span for validation |
| `VALIDATION_MIN_CONFIDENCE` | float | `0.3` | Minimum average confidence for validation |
| `BACKEND_BASE_URL` | str | `http://localhost:8080` | FastAPI backend base URL |
| `BACKEND_API_PREFIX` | str | `/api/v1` | Backend API version prefix |
| `BACKEND_REQUEST_TIMEOUT_SECONDS` | float | `5.0` | HTTP request timeout |
| `BACKEND_MAX_RETRIES` | int | `3` | Max retries for 5xx/network errors |
| `BACKEND_RETRY_DELAY_SECONDS` | float | `1.0` | Initial exponential backoff delay |
| `BACKEND_QUEUE_MAX_SIZE` | int | `100` | Max queued validated detections |
| `BACKEND_DUPLICATE_COOLDOWN_SECONDS`| float | `10.0` | Duplicate suppression window per track |

---

## Running the Service

### Run Locally
```bash
python -m app.main
```

### Run Tests
```bash
PYTHONPATH=. pytest tests -v
```

All 84 tests cover unit and integration behaviors:
- Deterministic frame sampling
- YOLO inference and confidence filtering
- Object tracking and track continuity across occlusions
- Temporal sliding window validation
- HTTP payload building with zero fabricated GPS
- Fast-fail on HTTP 4xx client errors
- Exponential backoff retries on HTTP 5xx server errors and network timeouts
- Bounded sender queue and documented drop policy
- Pipeline resilience against backend downtime
