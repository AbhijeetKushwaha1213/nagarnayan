# 🏙️ Nagar Nayan — Backend

> **Nagar Nayan** ("Eyes of the City") is an AI-powered urban intelligence platform that uses cameras mounted on public buses as mobile sensing units to detect and track urban anomalies in real time.

---

## Architecture Overview

```
Bus Camera
    ↓
RTSP Video Stream
    ↓
Video Stream Server          ← already built (FFmpeg + MediaMTX, separate project)
    ↓
AI Video Intelligence Service  ← separate service (YOLO inference, tracking, validation)
    ↓
► Nagar Nayan Backend  ◄      ← THIS PROJECT
    ↓
PostgreSQL + PostGIS           ← Phase 2
    ↓
WebSocket / REST APIs
    ↓
React GIS Dashboard            ← separate project
```

This backend **does not** implement:
- RTSP ingestion or video streaming (handled by the separate FFmpeg/MediaMTX server)
- YOLO inference, OpenCV, or any AI/ML processing (handled by the AI service)
- Authentication (Phase 3)
- Event management or database tables (Phase 2)

---

## Technology Stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI 0.115 |
| ASGI server | Uvicorn |
| Configuration | Pydantic Settings v2 |
| ORM | SQLAlchemy 2.x (Phase 2) |
| Migrations | Alembic (Phase 2) |
| Database | PostgreSQL + PostGIS (Phase 2) |
| Testing | pytest + httpx |
| Runtime | Python 3.11+ |
| Containerisation | Docker + docker-compose |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py              # Application factory, CORS, lifecycle hooks, root endpoint
│   ├── core/
│   │   ├── config.py        # Pydantic Settings — all config from env vars
│   │   └── logging.py       # Structured logging setup
│   ├── api/
│   │   ├── router.py        # Central API router (/api/v1)
│   │   └── routes/
│   │       └── health.py    # GET /api/v1/health
│   ├── models/              # SQLAlchemy models (Phase 2)
│   ├── schemas/             # Pydantic request/response schemas (Phase 2)
│   ├── services/            # Business logic (Phase 2+)
│   ├── repositories/        # Database access layer (Phase 2+)
│   └── utils/               # Shared helpers
├── tests/
│   └── test_health.py       # pytest tests for health & root endpoints
├── alembic/                 # Database migrations (Phase 2)
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── .env.example             # Configuration template
├── .gitignore
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml           # pytest configuration
├── requirements.txt
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11 or newer
- `pip` / a virtual environment manager

### 1 — Clone & set up the environment

```bash
# From the repo root
cd backend

# Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2 — Configure environment variables

```bash
cp .env.example .env
# Edit .env with your preferred values (defaults work for local dev)
```

### 3 — Run the development server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at **http://localhost:8000**.

---

## Running with Docker

```bash
# Build and start
docker-compose up --build

# Stop
docker-compose down
```

---

## Running Tests

```bash
# From the backend/ directory with the venv active
pytest

# Verbose output
pytest -v

# With coverage (requires pytest-cov)
pytest --cov=app --cov-report=term-missing
```

---

## Available Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Service identification — name, version, env |
| `GET` | `/api/v1/health` | Liveness probe |
| `GET` | `/docs` | Swagger / OpenAPI UI |
| `GET` | `/redoc` | ReDoc API documentation |

### Example — Health check

```bash
curl http://localhost:8000/api/v1/health
```

```json
{
  "status": "healthy",
  "service": "nagar-nayan-backend"
}
```

---

## Configuration Reference

All settings are loaded from environment variables (or `.env`).

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `Nagar Nayan Backend` | Service display name |
| `APP_ENV` | `development` | Environment tag |
| `APP_HOST` | `0.0.0.0` | Bind host |
| `APP_PORT` | `8000` | Bind port |
| `APP_VERSION` | `0.1.0` | Semantic version |
| `DATABASE_URL` | _(empty)_ | PostgreSQL DSN — **Phase 2** |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | Python log level |

---

## Roadmap

### Phase 1 — Foundation ✅ (current)
- FastAPI application factory with CORS
- Environment-based configuration via Pydantic Settings
- Structured logging
- Health & root endpoints
- pytest suite
- Docker support

### Phase 2 — Database
- PostgreSQL + PostGIS via SQLAlchemy 2.x async
- Alembic migrations
- Bus, Camera, and Detection entity models
- Repository layer

### Phase 3 — AI Integration
- REST endpoints to receive detection events from the AI Video Intelligence Service
- WebSocket event broadcasting to the React GIS Dashboard

### Phase 4 — Security & Ops
- JWT authentication
- Role-based access control
- Metrics / tracing
- CI/CD pipeline

---

## License

MIT
