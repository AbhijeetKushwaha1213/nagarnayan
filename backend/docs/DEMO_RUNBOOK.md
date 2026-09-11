# Nagar Nayan — End-to-End Demo Runbook (Phase 9)

This guide documents the exact, reproducible operational sequence for running the end-to-end Nagar Nayan demonstration pipeline:
`Video Stream Simulation Server -> RTSP -> AI Service -> Detection Ingestion -> Event Correlation -> Severity/Alert Engine -> PostgreSQL/PostGIS -> WebSocket -> React GIS Dashboard`.

---

## 1. Environment & Configuration Requirements

Before running the pipeline, ensure the following environment variables are configured. **Never commit actual production secrets or database credentials into source control.**

### Backend (`backend/.env`)
```bash
# Environment Mode
ENVIRONMENT=development
LOG_LEVEL=INFO

# Database Connection (PostgreSQL with PostGIS extension enabled)
# Note: Use your PostgreSQL connection string or Supabase pooler
DATABASE_URL=postgresql+asyncpg://<USER>:<PASSWORD>@<HOST>:<PORT>/<DATABASE>

# Server Host and Port
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8080

# CORS Configuration
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

### AI Service (`ai-service/.env` or exported in shell)
```bash
# Stream and Backend Targets
AI_RTSP_URL=rtsp://localhost:8554/bus/front
AI_BACKEND_URL=http://localhost:8080/api/v1/detections

# Model and Detection Parameters
AI_MODEL_PATH=yolov8n.pt
AI_CONFIDENCE_THRESHOLD=0.35
AI_TARGET_FPS=5
AI_MIN_FRAMES_VALIDATION=3

# Demo Fleet Entity Association
AI_BUS_ID=00000000-0000-0000-0000-000000000001
AI_CAMERA_ID=00000000-0000-0000-0000-000000000001
AI_STREAM_ID=00000000-0000-0000-0000-000000000001

# Controlled Demo Telemetry Configuration (Task 2)
# When enabled, attaches deterministic demo GPS coordinates with explicit DEMO provenance
DEMO_TELEMETRY_ENABLED=true
DEMO_TELEMETRY_LATITUDE=28.6139
DEMO_TELEMETRY_LONGITUDE=77.2090
DEMO_TELEMETRY_ROUTE_ID=ROUTE-DELHI-01
```

### Frontend (`frontend/.env` or default config)
```bash
VITE_API_BASE_URL=http://localhost:8080/api/v1
VITE_WS_URL=ws://localhost:8080/api/v1/ws
```

---

## 2. Step-by-Step Startup Sequence

Follow these 8 steps in order:

### Step 1: Start PostgreSQL / PostGIS
Ensure your local PostgreSQL database with PostGIS or Supabase project is active and accepting connections.
To verify connection:
```bash
cd backend
.venv/bin/python -c "
import asyncio, asyncpg
async def check():
    conn = await asyncpg.connect('<YOUR_DATABASE_URL>')
    print('DB Connection Successful:', await conn.fetchval('SELECT version();'))
    await conn.close()
# asyncio.run(check())
"
```

### Step 2: Start Backend
In a terminal, start the FastAPI ASGI server:
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8080
```
Verify health:
```bash
curl http://localhost:8080/api/v1/health
# Expected output: {"status":"healthy","database":"connected",...}
```

### Step 3: Seed Demo Bus, Camera, and Stream Records
Execute the idempotent seed script to ensure deterministic fleet records exist in the database:
```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/seed_demo_fleet.py
```
This guarantees the existence of:
- **Bus**: `DL-01-NN-1001` (ID: `00000000-0000-0000-0000-000000000001`)
- **Camera**: `front` (ID: `00000000-0000-0000-0000-000000000001`)
- **Stream**: `rtsp://localhost:8554/bus/front` (ID: `00000000-0000-0000-0000-000000000001`)

### Step 4: Start MediaMTX / Video Stream Server
In a separate terminal, launch the local MediaMTX RTSP server and FFmpeg looping publisher:
```bash
cd stream_server
./start-local.sh
```
Verify the stream is reachable:
```bash
python test-stream.py
# Expected output: Stream reachable, 25 frames decoded at 1280x720.
```

### Step 5: Start AI Video Intelligence Service
In a separate terminal, launch the AI service connected to the local RTSP feed:
```bash
cd ai-service
source ../backend/.venv/bin/activate
DEMO_TELEMETRY_ENABLED=true python run.py
```
Or run automated inference test:
```bash
DEMO_TELEMETRY_ENABLED=true python -c "
import asyncio
from app.pipeline.runner import PipelineRunner
from app.core.config import get_settings
settings = get_settings()
runner = PipelineRunner(settings)
asyncio.run(runner.run(max_frames=50))
"
```

### Step 6: Start Frontend Development Server
In a separate terminal, launch the React/Vite GIS Dashboard:
```bash
cd frontend
npm run dev -- --port 3000 --host 0.0.0.0
```

### Step 7: Open Dashboard
Open your browser and navigate to:
```
http://localhost:3000
```
Inspect the interface:
- **Header**: Connection indicator should show green (`LIVE CONNECTED` to `ws://localhost:8080/api/v1/ws`).
- **Dashboard**: High-level KPIs, recent urban events, and critical alerts.
- **Urban Events**: Filterable table of correlated events with severity badges and observation counts.
- **Alerts**: Municipal alert management table with lifecycle controls (Acknowledge / Resolve).
- **GIS Map**: Leaflet map centered on active event clusters.

### Step 8: Observe Live Pipeline Integration
1. The AI service processes RTSP frames at the configured FPS (e.g. 5 FPS).
2. Validated detections are POSTed to `http://localhost:8080/api/v1/detections`.
3. The Backend Event Correlation engine checks spatial (e.g. 30m) and temporal (e.g. 300s) proximity.
4. Qualifying events trigger the Severity and Alert engines.
5. The WebSocket publisher broadcasts `event.created`, `event.updated`, and `alert.created` / `alert.updated` envelopes.
6. The React `RealtimeContext` ingests envelopes, deduplicates by UUID, and updates UI state and map markers in real time.

---

## 3. Automated End-to-End Verification

To verify the pipeline automatically, execute:
```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/verify_e2e_pipeline.py
```

The verification suite executes in two clearly demarcated sections:
- **[SECTION A] REAL AI E2E PIPELINE VERIFICATION**:
  - Connects to the live RTSP stream (`rtsp://localhost:8554/bus/front`).
  - Executes live YOLOv8n object detection, ByteTrack tracking, and MultiFrameValidator.
  - Submits genuine validated detections (`VEHICLE` / `PEDESTRIAN`) via `DetectionSender`.
  - Asserts HTTP 201 backend ingestion and corresponding Urban Event creation.
  - Verifies real-time WebSocket delivery and GIS coordinate mapping.
- **[SECTION B] BACKEND SYNTHETIC CONTRACT & EDGE-CASE VERIFICATION**:
  - Validates spatial clustering proximity (~5m correlation).
  - Validates frame reference idempotency deduplication.
  - Validates distant observation separation (>5km).
  - Validates missing GPS handling.
  - Validates municipal alert synthesis, lifecycle transitions, and escalation.

When all criteria are met, the script will output:
```
======================================================================
ALL PHASE 9.1 END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY!
======================================================================
```
