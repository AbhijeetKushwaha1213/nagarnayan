"""
Health check route — GET /api/v1/health

Returns application and database health status.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.database import check_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class DatabaseHealth(BaseModel):
    status: str  # healthy | unhealthy | not_configured
    detail: str


class HealthResponse(BaseModel):
    """Schema for the health-check response."""

    status: str       # healthy | degraded
    service: str
    database: DatabaseHealth


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description=(
        "Returns liveness and database connectivity status. "
        "Overall status is 'healthy' when the database is reachable, "
        "'degraded' if the database is configured but unreachable."
    ),
)
async def health_check() -> HealthResponse:
    """Probe application and database health."""
    logger.debug("Health check requested")

    db_status, db_detail = await check_db_connection()

    # Determine overall status
    if db_status == "unhealthy":
        overall = "degraded"
    else:
        overall = "healthy"

    return HealthResponse(
        status=overall,
        service="nagar-nayan-backend",
        database=DatabaseHealth(status=db_status, detail=db_detail),
    )
