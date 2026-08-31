# Nagar Nayan — Video Streaming Server

A lightweight, standalone video stream simulation server. It transforms prerecorded bus/road camera videos into continuous, real-time live **RTSP** camera feeds for downstream consumption.

---

## 🎯 Architecture

```text
Recorded Video File (.mp4)
        ↓
FFmpeg continuously processes video (real-time pacing)
        ↓
Video is replayed in real time (infinite loop)
        ↓
MediaMTX Streaming Server
        ↓
Live RTSP Stream
        ↓
External Consumers (AI workers / OpenCV / VLC / ffplay)
```

```text
┌──────────────────────────────────────────────┐
│                nn-streamer                   │
│                                              │
│  - Reads videos/bus_front_01.mp4             │
│  - Loops continuously (-stream_loop -1)      │
│  - Real-time pacing (-re)                    │
│  - Publishes to rtsp://mediamtx:8554/bus/front│
└──────────────────────┬───────────────────────┘
                       │ RTSP Publish (TCP)
                       ▼
┌──────────────────────────────────────────────┐
│                nn-mediamtx                   │
│                                              │
│  - High-performance RTSP / HLS media server  │
│  - Exposes port 8554 (RTSP)                  │
│  - Serves multiple clients concurrently      │
└──────────────────────┬───────────────────────┘
                       │
                       │ RTSP Stream
                       ▼
        rtsp://localhost:8554/bus/front
```

---

## 📁 Directory Structure

```text
stream_server/
├── docker-compose.yml        # Multi-container orchestration (MediaMTX + Streamer)
├── README.md                 # Server documentation and testing guide
├── .env.example              # Sample environment configuration
│
├── mediamtx/
│   └── mediamtx.yml          # MediaMTX configuration
│
├── videos/
│   ├── bus_front_01.mp4      # Default recorded footage (simulated camera source)
│   └── README.md             # Guide on adding/swapping footage
│
├── streamer/
│   ├── Dockerfile            # Minimal Alpine + FFmpeg image
│   ├── start-stream.sh       # Streamer entrypoint with loop, retry & health check
│   └── README.md             # Streamer component documentation
│
└── scripts/
    ├── verify-stream.sh      # Bash script to test ffprobe & frame decoding
    └── test-stream.py        # OpenCV Python test client
```

---

## 🚀 Quick Start

### 1. Start the Server

From the `stream_server` directory:

```bash
docker compose up --build
```

To run in the background (detached mode):

```bash
docker compose up -d --build
```

### 2. Inspect Logs

```bash
docker compose logs -f
```

You will see clean startup and streaming logs:

```text
nn-streamer  | [STREAMER] ------------------------------------------------------------
nn-streamer  | [STREAMER] Starting video stream
nn-streamer  | [STREAMER] ------------------------------------------------------------
nn-streamer  | [STREAMER] Input:       bus_front_01.mp4 (/videos/bus_front_01.mp4)
nn-streamer  | [STREAMER] Stream path: /bus/front
nn-streamer  | [STREAMER] Publish URL: rtsp://mediamtx:8554/bus/front
nn-streamer  | [STREAMER] Transport:   tcp   Copy: false   FPS: 25
nn-streamer  | [STREAMER] ------------------------------------------------------------
nn-streamer  | [STREAMER] Connecting to MediaMTX...
nn-streamer  | [STREAMER] MediaMTX is reachable.
nn-streamer  | [STREAMER] Publishing live stream — source: file bus_front_01.mp4 (looping)
nn-streamer  | [STREAMER] Stream active → rtsp://mediamtx:8554/bus/front
```

---

## 📺 How to Test the Stream

The simulated live stream is available at:
```text
rtsp://localhost:8554/bus/front
```

### Option A: Using `ffplay`

```bash
ffplay -rtsp_transport tcp rtsp://localhost:8554/bus/front
```

### Option B: Using VLC Media Player

1. Open **VLC**.
2. Go to **File** → **Open Network...** (or press `Cmd+N` / `Ctrl+N`).
3. Enter URL: `rtsp://localhost:8554/bus/front`.
4. Click **Open**.

### Option C: Using OpenCV (Python)

Run the included verification script:

```bash
python3 scripts/test-stream.py
```

To display live frames in a window:

```bash
python3 scripts/test-stream.py --show
```

To test infinite streaming:

```bash
python3 scripts/test-stream.py --frames 0
```

### Option D: Using the Verification Script

```bash
./scripts/verify-stream.sh
```

---

## ⚙️ Configuration & Customization

Copy `.env.example` to `.env` to customize settings:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `RTSP_PORT` | `8554` | Host RTSP listening port |
| `HLS_PORT` | `8888` | Host HLS listening port |
| `VIDEO_FILE` | `bus_front_01.mp4` | Name of MP4 video file inside `./videos/` |
| `STREAM_PATH` | `bus/front` | Mount point URL path (`rtsp://localhost:8554/<STREAM_PATH>`) |
| `TARGET_FPS` | `25` | Output frame rate |
| `STREAM_COPY` | `false` | Set to `true` to skip re-encoding when using H.264 source |
| `RETRY_DELAY` | `3` | Delay (seconds) before retrying connections |

---

## 🔁 Continuous Looping & Reliability

- **Seamless loop**: Uses FFmpeg's `-stream_loop -1` to repeat the video file infinitely.
- **Fail-safe outer loop**: The startup script automatically restarts FFmpeg if an unexpected decoder/network error occurs.
- **Docker restart policies**: Both services use `restart: unless-stopped` for automated recovery.
- **Startup readiness probe**: The streamer tests TCP connectivity to MediaMTX before streaming, avoiding premature failures.

---

## 🔮 Scalability & Adding Additional Cameras

MediaMTX uses a catch-all configuration (`all_others`), allowing additional camera streams with zero MediaMTX config changes.

To add multiple camera feeds (e.g. `bus/NN-001/front`, `bus/NN-001/rear`), simply define additional streamer services in `docker-compose.yml`:

```yaml
  streamer-bus1-rear:
    build: ./streamer
    container_name: nn-streamer-bus1-rear
    restart: unless-stopped
    depends_on:
      - mediamtx
    environment:
      MEDIAMTX_HOST: mediamtx
      MEDIAMTX_RTSP_PORT: 8554
      VIDEO_FILE: bus_rear_01.mp4
      STREAM_PATH: bus/NN-001/rear
    volumes:
      - ./videos:/videos:ro
    networks:
      - streamnet
```

---

## 🛑 Stopping the Server

```bash
docker compose down
```
