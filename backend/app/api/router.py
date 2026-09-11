"""
Central API router — v1.

All feature routers are registered here.
main.py mounts this single router so it never needs to know about individual
route modules.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import alerts, buses, cameras, detections, events, health, streams, ws

api_router = APIRouter(prefix="/api/v1")

# ── Registered route modules ────────────────────────────────────────────────
api_router.include_router(health.router)
api_router.include_router(buses.router)
api_router.include_router(cameras.router)
api_router.include_router(streams.router)
api_router.include_router(detections.router)
api_router.include_router(events.router)
api_router.include_router(alerts.router)
api_router.include_router(ws.router)
