"""
Metric service — read-side query layer over unified_metrics_cache.

The Celery worker WRITES to this table (via normalization.normalize_platform_row).
The API layer READS from it through this service. Keeping reads in one place
means we can add caching, DataLoader batching, or materialized views later
without touching every route.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, PlatformType, UnifiedMetricCache


class MetricServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class MetricService:
    """Query unified_metrics_cache for a specific client, always agency-scoped."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _verify_client_access(self, client_id: UUID, agency_id: UUID) -> Client:
        """Check the client exists and belongs to this agency."""
        result = await self.db.execute(
            select(Client).where(
                Client.id == client_id,
                Client.agency_id == agency_id,
            )
        )
        client = result.scalar_one_or_none()
        if client is None:
            raise MetricServiceError("Client not found.", 404)
        return client

    async def list_metrics(
        self,
        client_id: UUID,
        agency_id: UUID,
        platform: Optional[PlatformType] = None,
        metric_name: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 500,
    ) -> List[UnifiedMetricCache]:
        """
        Return raw metric rows, optionally filtered.

        - No filter combination is required — the frontend can ask for every
          metric for a client and filter client-side if needed.
        - Results are ordered by metric_date DESC, metric_name ASC, so the
          most recent data is at the top.
        - Hard cap of `limit` rows (default 500) to keep single requests sane.
        """
        await self._verify_client_access(client_id, agency_id)

        stmt = select(UnifiedMetricCache).where(
            UnifiedMetricCache.client_id == client_id
        )

        if platform is not None:
            stmt = stmt.where(UnifiedMetricCache.platform_type == platform)
        if metric_name:
            stmt = stmt.where(UnifiedMetricCache.metric_name == metric_name)
        if start_date is not None:
            start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
            stmt = stmt.where(UnifiedMetricCache.metric_date >= start_dt)
        if end_date is not None:
            end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
            stmt = stmt.where(UnifiedMetricCache.metric_date <= end_dt)

        stmt = stmt.order_by(
            UnifiedMetricCache.metric_date.desc(),
            UnifiedMetricCache.platform_type.asc(),
            UnifiedMetricCache.metric_name.asc(),
        ).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def daily_timeseries(
        self,
        client_id: UUID,
        agency_id: UUID,
        metric_name: str,
        platform: Optional[PlatformType] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[dict]:
        """
        Aggregate metric values by day, collapsing campaign-level rows into
        a single total per day. Handy for charting.

        Returns a list of {"date": "YYYY-MM-DD", "value": float, "platform": str | null}
        sorted ascending by date.
        """
        await self._verify_client_access(client_id, agency_id)

        # Group by metric_date (truncated to day) AND platform, so the caller
        # can see per-platform lines on the same chart.
        day_col = func.date_trunc("day", UnifiedMetricCache.metric_date).label("day")
        total_col = func.sum(UnifiedMetricCache.metric_value).label("total")

        stmt = (
            select(
                day_col,
                UnifiedMetricCache.platform_type.label("platform"),
                total_col,
            )
            .where(
                UnifiedMetricCache.client_id == client_id,
                UnifiedMetricCache.metric_name == metric_name,
            )
            .group_by(day_col, UnifiedMetricCache.platform_type)
            .order_by(day_col.asc())
        )

        if platform is not None:
            stmt = stmt.where(UnifiedMetricCache.platform_type == platform)
        if start_date is not None:
            start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
            stmt = stmt.where(UnifiedMetricCache.metric_date >= start_dt)
        if end_date is not None:
            end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
            stmt = stmt.where(UnifiedMetricCache.metric_date <= end_dt)

        result = await self.db.execute(stmt)
        rows = result.all()

        series: List[dict] = []
        for day_value, platform_value, total in rows:
            series.append(
                {
                    "date": day_value.date().isoformat() if day_value else None,
                    "platform": platform_value.value if platform_value else None,
                    "value": float(total or 0.0),
                }
            )
        return series

    async def summary(
        self,
        client_id: UUID,
        agency_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        Return a small summary dict for dashboard cards.

        Shape:
            {
                "row_count": 1234,
                "platforms": ["meta_ads", "google_ads"],
                "metrics":   ["impressions", "clicks", "spend_usd"],
                "date_range": {"min": "2026-03-01", "max": "2026-04-18"}
            }
        """
        await self._verify_client_access(client_id, agency_id)

        stmt = select(
            func.count(UnifiedMetricCache.id),
            func.min(UnifiedMetricCache.metric_date),
            func.max(UnifiedMetricCache.metric_date),
        ).where(UnifiedMetricCache.client_id == client_id)

        if start_date is not None:
            start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
            stmt = stmt.where(UnifiedMetricCache.metric_date >= start_dt)
        if end_date is not None:
            end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
            stmt = stmt.where(UnifiedMetricCache.metric_date <= end_dt)

        result = await self.db.execute(stmt)
        count, min_date, max_date = result.one()

        # Distinct platforms + metrics for this client
        platforms_stmt = (
            select(UnifiedMetricCache.platform_type)
            .where(UnifiedMetricCache.client_id == client_id)
            .distinct()
        )
        platforms = [p.value for (p,) in (await self.db.execute(platforms_stmt)).all()]

        metrics_stmt = (
            select(UnifiedMetricCache.metric_name)
            .where(UnifiedMetricCache.client_id == client_id)
            .distinct()
        )
        metrics = [m for (m,) in (await self.db.execute(metrics_stmt)).all()]

        return {
            "row_count": int(count or 0),
            "platforms": sorted(platforms),
            "metrics": sorted(metrics),
            "date_range": {
                "min": min_date.date().isoformat() if min_date else None,
                "max": max_date.date().isoformat() if max_date else None,
            },
        }
