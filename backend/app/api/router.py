"""
Central API router — v1.

All feature routers are registered here.
main.py mounts this single router so it never needs to know about individual
route modules.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import health

api_router = APIRouter(prefix="/api/v1")

# ── Registered route modules ────────────────────────────────────────────────
# Each feature area gets its own router added here as the project grows.
api_router.include_router(health.router)
