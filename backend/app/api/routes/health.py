"""
Health check route — GET /api/v1/health

Returns a simple liveness response indicating the service is running.
No database probe in Phase 1; that will be added when PostgreSQL is wired in.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Schema for the health-check response."""

    status: str
    service: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description=(
        "Returns the current liveness status of the Nagar Nayan backend. "
        "A future version will also probe the database connection."
    ),
)
async def health_check() -> HealthResponse:
    """Liveness probe — confirms the application is running and reachable."""
    logger.debug("Health check requested")
    return HealthResponse(status="healthy", service="nagar-nayan-backend")
