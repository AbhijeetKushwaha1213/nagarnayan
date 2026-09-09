"""
Nagar Nayan — FastAPI application entry point.

Responsibilities of this module:
  - Create and configure the FastAPI application instance.
  - Register middleware (CORS).
  - Mount the central API router.
  - Expose the root endpoint.

Everything else (config, logging, routes, business logic) lives in dedicated
sub-packages.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging

# ── Bootstrap logging before anything else runs ─────────────────────────────
setup_logging()
logger = logging.getLogger(__name__)

# ── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
    logger.info(
        "Starting %s v%s [env=%s]",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV,
    )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


# ── Application factory ──────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "AI-powered urban intelligence backend for Nagar Nayan. "
            "Receives structured detection metadata from the AI Video Intelligence "
            "Service and exposes it via REST and WebSocket APIs."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──────────────────────────────────────────────────────────────
    app.include_router(api_router)

    return app


# ── Application instance ─────────────────────────────────────────────────────
app = create_app()


# ── Root endpoint ────────────────────────────────────────────────────────────
@app.get("/", tags=["root"], summary="Service identification")
async def root() -> dict[str, str]:
    """
    Root endpoint — identifies the backend service.

    Useful for a quick sanity-check that the server is reachable.
    All functional endpoints are under /api/v1/.
    """
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "docs": "/docs",
        "api_prefix": "/api/v1",
    }
