# Nagar Nayan Backend

AI-powered urban intelligence backend — Phase 2.

The backend receives structured detection/event metadata from the **AI Video Intelligence Service** and exposes it via REST APIs. It manages the physical infrastructure (buses, cameras, streams) using PostgreSQL + PostGIS.

> **Important**: This backend does NOT handle RTSP streaming, video processing, or AI inference.  
> RTSP streaming is managed by a separate **FFmpeg + MediaMTX Video Stream Server**.  
> The `stream_url` field stores RTSP endpoint URLs as metadata only.

---

## Architecture

```
Bus Camera (physical hardware)
    ↓
RTSP Video Stream
    ↓
Video Stream Server [SEPARATE — FFmpeg + MediaMTX]
    ↓
AI Video Intelligence Service [FUTURE]
    ↓
┌─────────────────────────────────┐
│  Nagar Nayan Backend  ◄── HERE  │
│  FastAPI + PostgreSQL/PostGIS   │
└─────────────────────────────────┘
    ↓
REST APIs
    ↓
React GIS Dashboard [FUTURE]
```

---

## Database Architecture

```
Bus
 └── Camera (1 bus → many cameras)
      └── Stream (1 camera → many streams)

Future hierarchy (Phase 3+):
Stream → Detection → Event → Alert
```

### Tables

| Table     | Description                               |
|-----------|-------------------------------------------|
| `buses`   | Physical bus vehicles                     |
| `cameras` | Cameras mounted on buses                  |
| `streams` | RTSP stream metadata (URLs only, no ingestion) |

### Bus

| Column       | Type      | Notes                          |
|--------------|-----------|--------------------------------|
| `id`         | UUID      | Primary key                    |
| `bus_number` | VARCHAR   | Unique fleet/registration ID   |
| `route_id`   | VARCHAR   | Route identifier (nullable)    |
| `status`     | ENUM      | `active` / `inactive`          |
| `created_at` | TIMESTAMPTZ | Server default               |
| `updated_at` | TIMESTAMPTZ | Server default               |

### Camera

| Column        | Type    | Notes                                          |
|---------------|---------|------------------------------------------------|
| `id`          | UUID    | Primary key                                    |
| `bus_id`      | UUID    | FK → buses.id (CASCADE DELETE)                 |
| `camera_type` | ENUM    | `front` / `rear` / `side` / `interior`         |
| `status`      | ENUM    | `active` / `inactive` / `error`                |
| `created_at`  | TIMESTAMPTZ |                                            |
| `updated_at`  | TIMESTAMPTZ |                                            |

### Stream

| Column       | Type    | Notes                                              |
|--------------|---------|----------------------------------------------------|
| `id`         | UUID    | Primary key                                        |
| `camera_id`  | UUID    | FK → cameras.id (CASCADE DELETE)                   |
| `stream_url` | VARCHAR | RTSP URL — metadata only, NOT consumed by backend  |
| `protocol`   | ENUM    | `rtsp`                                             |
| `status`     | ENUM    | `active` / `inactive` / `error`                    |
| `started_at` | TIMESTAMPTZ | Set by AI service                              |
| `stopped_at` | TIMESTAMPTZ | Set by AI service                              |
| `created_at` | TIMESTAMPTZ |                                                |
| `updated_at` | TIMESTAMPTZ |                                                |

---

## Local Development Setup

### Prerequisites

- Python 3.11+ (3.14 supported but asyncpg requires Docker for DB tests)
- Docker + Docker Compose
- Git

### Steps

```bash
# 1. Clone and enter the backend directory
cd backend/

# 2. Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Copy environment file
cp .env.example .env
# Edit .env with your values if needed

# 4. Start the server (without DB — Phase 1 endpoints available)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

---

## Docker Setup (Full Stack — Recommended)

```bash
# Start all services (PostgreSQL + Backend)
docker compose up --build

# Start only the database
docker compose up -d db

# View logs
docker compose logs -f backend
docker compose logs -f db

# Stop everything
docker compose down

# Stop and remove volumes (WARNING: deletes all data)
docker compose down -v
```

---

## Database Migrations

```bash
# Run all migrations (creates tables)
alembic upgrade head

# Roll back one revision
alembic downgrade -1

# Show current revision
alembic current

# Show migration history
alembic history

# Auto-generate a new migration (after model changes)
alembic revision --autogenerate -m "description of change"
```

> **Note**: Alembic uses the `psycopg2` sync driver. The app uses `asyncpg`.  
> Set `DATABASE_URL` environment variable before running migrations:
> ```bash
> export DATABASE_URL=postgresql+asyncpg://nagarnayan:secret@localhost:5432/nagar_nayan
> alembic upgrade head
> ```

---

## Test Commands

```bash
# Phase 1 tests (no database required)
pytest tests/test_health.py -v

# All tests (Phase 2 tests skipped without DATABASE_URL)
pytest -v

# Phase 2 DB tests (requires Docker DB + migrations)
docker compose up -d db
export DATABASE_URL=postgresql+asyncpg://nagarnayan:secret@localhost:5432/nagar_nayan
alembic upgrade head
pytest -v

# Run specific test file
pytest tests/test_buses.py -v

# With coverage
pytest --cov=app -v
```

---

## API Endpoints

Base URL: `http://localhost:8080/api/v1`  
Interactive docs: `http://localhost:8080/docs`

### Health

| Method | Path               | Description              |
|--------|--------------------|--------------------------|
| `GET`  | `/health`          | App + database health    |

### Buses

| Method   | Path              | Description         |
|----------|-------------------|---------------------|
| `GET`    | `/buses`          | List all buses      |
| `GET`    | `/buses/{id}`     | Get bus by ID       |
| `POST`   | `/buses`          | Create bus          |
| `PATCH`  | `/buses/{id}`     | Update bus          |
| `DELETE` | `/buses/{id}`     | Delete bus          |

### Cameras

| Method   | Path                     | Description                          |
|----------|--------------------------|--------------------------------------|
| `GET`    | `/cameras`               | List cameras (optional `?bus_id=`)   |
| `GET`    | `/cameras/{id}`          | Get camera by ID                     |
| `POST`   | `/cameras`               | Create camera                        |
| `PATCH`  | `/cameras/{id}`          | Update camera                        |
| `DELETE` | `/cameras/{id}`          | Delete camera                        |

### Streams

| Method   | Path                     | Description                              |
|----------|--------------------------|------------------------------------------|
| `GET`    | `/streams`               | List streams (optional `?camera_id=`)    |
| `GET`    | `/streams/{id}`          | Get stream by ID                         |
| `POST`   | `/streams`               | Register stream metadata                 |
| `PATCH`  | `/streams/{id}`          | Update stream metadata                   |
| `DELETE` | `/streams/{id}`          | Delete stream metadata                   |

### Detections (AI Ingestion Contract — Phase 4A)

| Method   | Path                     | Description                                          |
|----------|--------------------------|------------------------------------------------------|
| `POST`   | `/detections`            | Ingest raw AI detection metadata from AI service     |
| `GET`    | `/detections`            | List detections with filtering (bus, camera, etc.)   |
| `GET`    | `/detections/{id}`       | Retrieve detection details by ID                     |


---

## Example API Requests

### Create a Bus

```bash
curl -s -X POST http://localhost:8080/api/v1/buses \
  -H "Content-Type: application/json" \
  -d '{"bus_number": "KA-01-1234", "route_id": "ROUTE-7", "status": "active"}' \
  | python3 -m json.tool
```

### Create a Camera on that Bus

```bash
curl -s -X POST http://localhost:8080/api/v1/cameras \
  -H "Content-Type: application/json" \
  -d '{"bus_id": "<BUS_UUID>", "camera_type": "front"}' \
  | python3 -m json.tool
```

### Register a Stream (RTSP URL metadata only)

```bash
curl -s -X POST http://localhost:8080/api/v1/streams \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "<CAMERA_UUID>",
    "stream_url": "rtsp://stream-server:8554/bus/KA-01-1234/front",
    "protocol": "rtsp"
  }' \
  | python3 -m json.tool
```

### Check Health

```bash
curl -s http://localhost:8080/api/v1/health | python3 -m json.tool
```

Expected response (with DB running):
```json
{
  "status": "healthy",
  "service": "nagar-nayan-backend",
  "database": {
    "status": "healthy",
    "detail": "OK"
  }
}
```

### Submit an AI Detection (Phase 4A)

```bash
curl -s -X POST http://localhost:8080/api/v1/detections \
  -H "Content-Type: application/json" \
  -d '{
    "bus_id": "<BUS_UUID>",
    "camera_id": "<CAMERA_UUID>",
    "stream_id": "<STREAM_UUID>",
    "detection_type": "POTHOLE",
    "confidence": 0.92,
    "latitude": 12.9716,
    "longitude": 77.5946,
    "detected_at": "2026-09-10T10:30:22Z",
    "frame_reference": "frame_000123",
    "metadata": {
      "model": "yolo",
      "model_version": "v1",
      "class_id": 3,
      "tracking_id": 42,
      "bounding_box": {
        "x1": 100,
        "y1": 200,
        "x2": 300,
        "y2": 400
      }
    }
  }' \
  | python3 -m json.tool
```


---

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── buses.py      # Bus CRUD endpoints
│   │   │   ├── cameras.py    # Camera CRUD endpoints
│   │   │   ├── health.py     # Health check
│   │   │   └── streams.py    # Stream metadata endpoints
│   │   └── router.py         # Central API router
│   ├── core/
│   │   ├── config.py         # Pydantic Settings
│   │   ├── database.py       # Engine, session, Base, get_db
│   │   └── logging.py        # Structured logging setup
│   ├── models/
│   │   ├── base.py           # TimestampMixin
│   │   ├── bus.py            # Bus model + BusStatus
│   │   ├── camera.py         # Camera model + enums
│   │   └── stream.py         # Stream model + enums
│   ├── repositories/
│   │   ├── base.py           # Generic BaseRepository
│   │   ├── bus.py            # BusRepository
│   │   ├── camera.py         # CameraRepository
│   │   └── stream.py         # StreamRepository
│   ├── schemas/
│   │   ├── bus.py            # BusCreate, BusUpdate, BusResponse
│   │   ├── camera.py         # CameraCreate, CameraUpdate, CameraResponse
│   │   └── stream.py         # StreamCreate, StreamUpdate, StreamResponse
│   ├── services/
│   │   ├── bus.py            # BusService (business logic)
│   │   ├── camera.py         # CameraService
│   │   └── stream.py         # StreamService
│   └── main.py               # FastAPI app factory
├── alembic/
│   ├── versions/
│   │   └── 0001_initial.py   # PostGIS + buses + cameras + streams
│   └── env.py                # Alembic configuration
├── tests/
│   ├── conftest.py           # Fixtures, requires_db marker
│   ├── test_health.py        # Phase 1 + Phase 2 health tests
│   ├── test_buses.py         # Bus CRUD tests
│   ├── test_cameras.py       # Camera CRUD tests
│   └── test_streams.py       # Stream CRUD tests
├── .env.example              # Environment template
├── docker-compose.yml        # PostgreSQL + Backend
├── Dockerfile
└── requirements.txt
```

---

## AI Video Intelligence Ingestion Contract (Phase 4A)

This document establishes the production-ready ingestion contract between the external **AI Video Intelligence Service** and the **Nagar Nayan Backend**.

### Architecture & Pipeline

```
RTSP Video Stream (Bus Cameras)
    ↓
AI Service (OpenCV → YOLO → Object Tracking → Validation)
    ↓
Detection Metadata (JSON)
    ↓
HTTP POST /api/v1/detections
    ↓
Nagar Nayan Backend (FastAPI + PostgreSQL/PostGIS)
```

> **Strict Architectural Rule**: The backend does NOT process video or connect to RTSP/YOLO. It receives validated, structured JSON metadata from the AI service via HTTP POST.

### Ingestion Request Specification

- **Method**: `POST`
- **Path**: `/api/v1/detections`
- **Content-Type**: `application/json`
- **Success Status**: `201 Created`

#### Request Payload Fields

| Field | Type | Required | Description | Example |
|---|---|---|---|---|
| `bus_id` | UUID | **Yes** | ID of the physical bus | `"9316d3f2-c93d-4c57-8975-f37e61e01861"` |
| `camera_id` | UUID | **Yes** | ID of the camera mounted on the bus | `"4a6566b6-8bb0-4965-b778-904ec17b8f60"` |
| `stream_id` | UUID | *Optional* | ID of the active video stream | `"5b0f4415-dc56-4cf3-a7be-76673ebf1974"` |
| `detection_type` | String | **Yes** | Category of detected issue (e.g. `POTHOLE`, `DAMAGED_ROAD`) | `"POTHOLE"` |
| `confidence` | Float | **Yes** | Confidence score between `0.0` and `1.0` | `0.92` |
| `latitude` | Float | *Optional* | WGS84 Latitude between `-90.0` and `90.0` | `12.9716` |
| `longitude` | Float | *Optional* | WGS84 Longitude between `-180.0` and `180.0` | `77.5946` |
| `detected_at` | String (ISO 8601) | **Yes** | Timezone-aware timestamp when detection occurred | `"2026-09-10T10:30:22Z"` |
| `frame_reference` | String | *Optional* | AI frame/snapshot identifier (used for idempotency) | `"frame_000123"` |
| `metadata` | Object | *Optional* | Arbitrary model telemetry (bounding boxes, track ID, etc.) | `{ "model": "yolo", "class_id": 3 }` |

#### Example Ingestion Request

```json
{
  "camera_id": "4a6566b6-8bb0-4965-b778-904ec17b8f60",
  "bus_id": "9316d3f2-c93d-4c57-8975-f37e61e01861",
  "stream_id": "5b0f4415-dc56-4cf3-a7be-76673ebf1974",
  "detection_type": "POTHOLE",
  "confidence": 0.92,
  "latitude": 12.9716,
  "longitude": 77.5946,
  "detected_at": "2026-09-10T10:30:22Z",
  "frame_reference": "frame_000123",
  "metadata": {
    "model": "yolo",
    "model_version": "v1",
    "class_id": 3,
    "tracking_id": 45,
    "bounding_box": {
      "x1": 100,
      "y1": 200,
      "x2": 300,
      "y2": 400
    }
  }
}
```

### Ingestion Response Specification

The response returns clean metadata without leaking internal database columns. Both `detection_id` and `id` are provided for client contract compatibility.

```json
{
  "detection_id": "c7a884e2-6366-4e58-9a3d-4ef1e4f48b11",
  "id": "c7a884e2-6366-4e58-9a3d-4ef1e4f48b11",
  "bus_id": "9316d3f2-c93d-4c57-8975-f37e61e01861",
  "camera_id": "4a6566b6-8bb0-4965-b778-904ec17b8f60",
  "stream_id": "5b0f4415-dc56-4cf3-a7be-76673ebf1974",
  "detection_type": "POTHOLE",
  "confidence": 0.92,
  "latitude": 12.9716,
  "longitude": 77.5946,
  "detected_at": "2026-09-10T10:30:22Z",
  "frame_reference": "frame_000123",
  "metadata": {
    "model": "yolo",
    "model_version": "v1",
    "class_id": 3,
    "tracking_id": 45,
    "bounding_box": {
      "x1": 100,
      "y1": 200,
      "x2": 300,
      "y2": 400
    }
  },
  "event_id": null,
  "created_at": "2026-09-10T10:30:22.789123Z"
}
```

### Source Hierarchy Validation

The backend guarantees physical infrastructure integrity before ingesting detections:

```
Bus
 ↓ (must belong to Bus)
Camera
 ↓ (must belong to Camera)
Stream
```

Validation rules:
- **Bus Existence**: `bus_id` must resolve to an existing bus; otherwise returns `422 Unprocessable Entity`.
- **Camera Existence**: `camera_id` must resolve to an existing camera; otherwise returns `422 Unprocessable Entity`.
- **Camera-Bus Ownership**: `camera.bus_id` must equal `bus_id`; mismatches return `422 Unprocessable Entity`.
- **Stream Existence**: If `stream_id` is provided, it must exist; otherwise returns `422 Unprocessable Entity`.
- **Stream-Camera Ownership**: If `stream_id` is provided, `stream.camera_id` must equal `camera_id`; mismatches return `422 Unprocessable Entity`.

All errors are returned as structured HTTP 422 errors without exposing raw PostgreSQL or SQLAlchemy exceptions.

### Idempotency & Retry Mechanism

Network disruptions or timeouts may lead the AI service to retry requests. To prevent creating duplicate detection records:
- A composite identity is evaluated: `(camera_id, frame_reference, detection_type)`.
- If the backend receives an identical detection from the same camera and frame reference, it returns the existing record instead of inserting a duplicate.

### AI Service Client Implementation Example (Python)

```python
import httpx
from datetime import datetime, timezone

BACKEND_BASE_URL = "http://localhost:8080/api/v1"

def submit_detection_to_backend(
    bus_id: str,
    camera_id: str,
    stream_id: str,
    detection_type: str,
    confidence: float,
    latitude: float,
    longitude: float,
    frame_ref: str,
    bbox: dict,
) -> dict:
    payload = {
        "bus_id": bus_id,
        "camera_id": camera_id,
        "stream_id": stream_id,
        "detection_type": detection_type,
        "confidence": confidence,
        "latitude": latitude,
        "longitude": longitude,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "frame_reference": frame_ref,
        "metadata": {
            "model": "yolo",
            "model_version": "v1",
            "bounding_box": bbox,
        },
    }

    with httpx.Client(base_url=BACKEND_BASE_URL, timeout=5.0) as client:
        response = client.post("/detections", json=payload)
        response.raise_for_status()
        return response.json()
```

---

## Real-Time WebSocket API (Phase 7)

The backend provides a real-time WebSocket connection for GIS dashboards and operational clients:

```
WS /api/v1/ws
```

### Connection Lifecycle & Behavior
- **No Authentication**: In this phase, clients connect directly without credentials (`ws://localhost:8080/api/v1/ws`).
- **In-Memory Connection Management**: Connected sockets are managed in-process via `ConnectionManager`.
- **Error Isolation**: Slow or abruptly disconnected clients are safely timed out (2.0s bounded send) and pruned without interrupting broadcasts to remaining clients.
- **Transaction Consistency**: Events and alerts are strictly broadcast **post-commit**. Database operations will never roll back due to a WebSocket network glitch, and phantom broadcasts are impossible.
- **Logical Ordering**: For newly synthesized actionable municipal issues, `event.created` is guaranteed to broadcast before `alert.created`.
- **Connection Acknowledgement & Keepalive**: Upon connection or sending `"connect"` / `"hello"`, the server responds with:
  ```json
  {
    "type": "system.connected",
    "timestamp": "2026-09-09T16:40:00.000000Z",
    "data": {
      "status": "connected",
      "active_clients": 1
    }
  }
  ```
  Clients may send `"ping"` or `{"type": "ping"}`; the server responds with:
  ```json
  {
    "type": "system.pong",
    "timestamp": "2026-09-09T16:40:00.000000Z",
    "data": { "status": "alive" }
  }
  ```

### Standard Message Envelope

All broadcast messages adhere to a uniform JSON envelope:

```json
{
  "type": "<message_type>",
  "timestamp": "<iso8601_utc_timestamp>",
  "data": { ... }
}
```

### Supported Message Types & Payloads

#### 1. `event.created`
Broadcast immediately after a new municipal `Event` is created and committed to the database.

```json
{
  "type": "event.created",
  "timestamp": "2026-09-09T16:40:00.123456Z",
  "data": {
    "id": "7b0a887b-6007-4f4b-84a1-8d26df85bcf6",
    "event_type": "POTHOLE",
    "severity": "HIGH",
    "status": "DETECTED",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "confidence": 0.88,
    "first_detected_at": "2026-09-09T16:39:55.000000Z",
    "last_detected_at": "2026-09-09T16:39:55.000000Z",
    "bus_id": "b1a1c9e4-1664-4d2b-8057-1614546ea3f9",
    "camera_id": "c2b2d8f5-2775-5e3c-9168-2725657fb4a0",
    "metadata": {
      "source": "automated_detection",
      "detection_count": 1
    }
  }
}
```
*Note: If GPS coordinates are unavailable, `latitude: null` and `longitude: null` are sent. Coordinates are never fabricated.*

#### 2. `event.updated`
Broadcast when an ongoing municipal `Event` receives additional correlated detections or is updated by an operator.

```json
{
  "type": "event.updated",
  "timestamp": "2026-09-09T16:41:00.654321Z",
  "data": {
    "id": "7b0a887b-6007-4f4b-84a1-8d26df85bcf6",
    "event_type": "POTHOLE",
    "severity": "HIGH",
    "status": "DETECTED",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "confidence": 0.91,
    "first_detected_at": "2026-09-09T16:39:55.000000Z",
    "last_detected_at": "2026-09-09T16:41:00.000000Z",
    "bus_id": "b1a1c9e4-1664-4d2b-8057-1614546ea3f9",
    "camera_id": "c2b2d8f5-2775-5e3c-9168-2725657fb4a0",
    "metadata": {
      "detection_count": 2
    }
  }
}
```

#### 3. `alert.created`
Broadcast when an actionable municipal `Alert` is synthesized from an Event.

```json
{
  "type": "alert.created",
  "timestamp": "2026-09-09T16:40:00.234567Z",
  "data": {
    "id": "e9b216f4-511d-4f85-afaa-9e547793c8c7",
    "event_id": "7b0a887b-6007-4f4b-84a1-8d26df85bcf6",
    "alert_type": "MUNICIPAL_ISSUE",
    "severity": "HIGH",
    "status": "NEW",
    "title": "High Priority Pothole Detected",
    "message": "Persistent pothole detected by bus-camera observations. Confidence: 0.88",
    "triggered_at": "2026-09-09T16:40:00.200000Z",
    "acknowledged_at": null,
    "resolved_at": null,
    "created_at": "2026-09-09T16:40:00.200000Z",
    "metadata": {
      "event_type": "POTHOLE",
      "event_severity": "HIGH"
    }
  }
}
```

#### 4. `alert.updated`
Broadcast when an `Alert` undergoes a lifecycle state transition (e.g., `NEW` → `ACKNOWLEDGED`, `ACKNOWLEDGED` → `RESOLVED`, or is escalated).

```json
{
  "type": "alert.updated",
  "timestamp": "2026-09-09T16:45:00.000000Z",
  "data": {
    "id": "e9b216f4-511d-4f85-afaa-9e547793c8c7",
    "event_id": "7b0a887b-6007-4f4b-84a1-8d26df85bcf6",
    "alert_type": "MUNICIPAL_ISSUE",
    "severity": "HIGH",
    "status": "ACKNOWLEDGED",
    "title": "High Priority Pothole Detected",
    "message": "Persistent pothole detected by bus-camera observations. Confidence: 0.88",
    "triggered_at": "2026-09-09T16:40:00.200000Z",
    "acknowledged_at": "2026-09-09T16:45:00.000000Z",
    "resolved_at": null,
    "created_at": "2026-09-09T16:40:00.200000Z",
    "metadata": {
      "event_type": "POTHOLE"
    }
  }
}
```

### Architectural Limitation & Future Clustering
- **Current Prototype**: The `ConnectionManager` maintains WebSocket client connections in process memory.
- **Production Clustering**: In a future phase with multiple backend worker replicas behind a load balancer, multi-node broadcasting will use a shared pub/sub layer (e.g. Redis Pub/Sub).

---

## What is NOT in this backend

| Capability              | Status / Where it lives             |
|-------------------------|------------------------------------|
| RTSP stream ingestion   | Video Stream Server (FFmpeg/MediaMTX) |
| Video processing        | AI Video Intelligence Service      |
| YOLO / AI inference     | AI Video Intelligence Service      |
| Detections, Events      | ✅ Completed (Phases 3-5)           |
| Alert Engine            | ✅ Completed (Phase 6)             |
| Real-time WebSockets    | ✅ Completed (Phase 7)             |
| Authentication & Users  | Future Phase                       |
| Redis / Celery          | Future Phase                       |
| React GIS Dashboard     | Frontend                           |
