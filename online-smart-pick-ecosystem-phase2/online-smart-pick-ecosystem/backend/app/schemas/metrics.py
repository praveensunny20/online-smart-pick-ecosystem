"""Pydantic schemas for the metrics and sync API routes."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import PlatformType


class MetricRowResponse(BaseModel):
    """One normalized metric row."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    platform_type: PlatformType
    metric_name: str
    metric_value: float
    metric_date: datetime
    campaign_id: Optional[str]
    campaign_name: Optional[str]
    fetched_at: datetime


class MetricTimeseriesPoint(BaseModel):
    date: Optional[str]
    platform: Optional[str]
    value: float


class MetricSummaryResponse(BaseModel):
    row_count: int
    platforms: List[str]
    metrics: List[str]
    date_range: Dict[str, Optional[str]]


class SyncTriggerResponse(BaseModel):
    """Response from POST /data/sync/{client_id}."""
    client_id: UUID
    task_id: str
    message: str
    status: str
