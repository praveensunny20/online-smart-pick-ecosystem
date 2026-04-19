"""
Metrics API routes.

    GET /clients/{client_id}/metrics           — List raw metric rows (filterable)
    GET /clients/{client_id}/metrics/timeseries — Daily aggregated series for charts
    GET /clients/{client_id}/metrics/summary   — Dashboard card summary
"""
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import AgencyUser, PlatformType
from app.schemas.metrics import (
    MetricRowResponse,
    MetricSummaryResponse,
    MetricTimeseriesPoint,
)
from app.services.metric_service import MetricService, MetricServiceError

router = APIRouter(prefix="/clients/{client_id}/metrics", tags=["metrics"])


@router.get(
    "",
    response_model=List[MetricRowResponse],
    summary="List normalized metrics for a client (optionally filtered)",
)
async def list_metrics(
    client_id: UUID,
    platform: Optional[PlatformType] = Query(
        None, description="Filter by platform (e.g. meta_ads, google_ads)."
    ),
    metric_name: Optional[str] = Query(
        None, description="Filter by unified metric name (e.g. impressions, clicks)."
    ),
    start_date: Optional[date] = Query(
        None, description="Inclusive start date (YYYY-MM-DD)."
    ),
    end_date: Optional[date] = Query(
        None, description="Inclusive end date (YYYY-MM-DD)."
    ),
    limit: int = Query(500, ge=1, le=2000),
    current_user: AgencyUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MetricService(db)
    try:
        rows = await service.list_metrics(
            client_id=client_id,
            agency_id=current_user.agency_id,
            platform=platform,
            metric_name=metric_name,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    except MetricServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return [MetricRowResponse.model_validate(r) for r in rows]


@router.get(
    "/timeseries",
    response_model=List[MetricTimeseriesPoint],
    summary="Daily aggregated series for a specific metric (chart-ready)",
)
async def metric_timeseries(
    client_id: UUID,
    metric_name: str = Query(..., description="Required unified metric name."),
    platform: Optional[PlatformType] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: AgencyUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MetricService(db)
    try:
        series = await service.daily_timeseries(
            client_id=client_id,
            agency_id=current_user.agency_id,
            metric_name=metric_name,
            platform=platform,
            start_date=start_date,
            end_date=end_date,
        )
    except MetricServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return [MetricTimeseriesPoint(**p) for p in series]


@router.get(
    "/summary",
    response_model=MetricSummaryResponse,
    summary="Summary of available metrics/platforms/date range for a client",
)
async def metric_summary(
    client_id: UUID,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: AgencyUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MetricService(db)
    try:
        summary = await service.summary(
            client_id=client_id,
            agency_id=current_user.agency_id,
            start_date=start_date,
            end_date=end_date,
        )
    except MetricServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return MetricSummaryResponse(**summary)
