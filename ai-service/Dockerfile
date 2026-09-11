# ─────────────────────────────────────────────────────────────────────────────
# Nagar Nayan — AI Video Intelligence Service Dockerfile
# Phase 1: RTSP Stream Consumer Foundation (CPU Only)
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build Dependencies ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime Image ───────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Minimal runtime libraries for OpenCV headless and networking
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application source and configuration
COPY app/ app/
COPY config/ config/

# Non-root user for security
RUN addgroup --system nagarnayan && adduser --system --ingroup nagarnayan nagarnayan
USER nagarnayan

CMD ["python", "-m", "app.main"]
