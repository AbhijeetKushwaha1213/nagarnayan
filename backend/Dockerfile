# ─────────────────────────────────────────────────────────────────────────────
# Nagar Nayan Backend — Dockerfile
#
# Multi-stage build:
#   builder  — installs dependencies into a venv
#   runtime  — lean final image with only the venv and app code
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System build deps (needed for some C-extension packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated virtual environment so the runtime stage is clean.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built venv from the builder stage.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source code.
COPY app/ app/

# Non-root user for security.
RUN addgroup --system nagarnayan && adduser --system --ingroup nagarnayan nagarnayan
USER nagarnayan

EXPOSE 8000

# Uvicorn runs the ASGI app; settings are controlled via environment variables.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
