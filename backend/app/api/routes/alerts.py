"""
Alert routes — REST API for municipal Alert management.

GET   /api/v1/alerts
GET   /api/v1/alerts/{alert_id}
PATCH /api/v1/alerts/{alert_id}
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.alert import AlertStatus, AlertType
from app.models.event import EventSeverity
from app.schemas.alert import AlertResponse, AlertUpdate
from app.services.alert import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _get_service(session: AsyncSession = Depends(get_db)) -> AlertService:
    return AlertService(session)


@router.get(
    "",
    response_model=list[AlertResponse],
    summary="List municipal alerts",
)
async def list_alerts(
    status: AlertStatus | None = Query(None, description="Filter by alert lifecycle status"),
    severity: EventSeverity | None = Query(None, description="Filter by severity"),
    event_id: uuid.UUID | None = Query(None, description="Filter by originating event ID"),
    alert_type: AlertType | None = Query(None, description="Filter by alert category"),
    limit: int = Query(100, ge=1, le=1000, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    service: AlertService = Depends(_get_service),
) -> list[AlertResponse]:
    """List municipal alerts matching specified filters with pagination."""
    return await service.list_alerts(
        status_filter=status,
        severity=severity,
        event_id=event_id,
        alert_type=alert_type,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Get alert by ID",
)
async def get_alert(
    alert_id: uuid.UUID,
    service: AlertService = Depends(_get_service),
) -> AlertResponse:
    """Retrieve details for a single municipal alert, including parent event summary."""
    return await service.get_alert(alert_id)


@router.patch(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Update alert status or metadata",
)
async def update_alert(
    alert_id: uuid.UUID,
    data: AlertUpdate,
    service: AlertService = Depends(_get_service),
) -> AlertResponse:
    """
    Perform lifecycle transitions on an alert (e.g. NEW -> ACKNOWLEDGED, ACKNOWLEDGED -> RESOLVED).

    Enforces valid lifecycle state machine transitions.
    """
    return await service.update_alert(alert_id, data)
