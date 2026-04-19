"""
Celery tasks that fetch data from platform connections and write it to
unified_metrics_cache.

Why this uses SYNC SQLAlchemy (psycopg2) instead of the async engine in
app.db.session:
    - Celery workers run in a normal OS thread per task, not an asyncio event
      loop. Using asyncpg inside a worker requires you to spin up an event
      loop per task, which is slow and fragile.
    - A dedicated sync engine with psycopg2 is simpler, faster under Celery,
      and the rest of the app is untouched (the async engine still handles
      every HTTP request).

The connection string is derived from settings.sync_database_url, which
just swaps the `postgresql+asyncpg://` prefix for `postgresql+psycopg2://`.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List
from uuid import UUID

from celery import shared_task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.encryption import get_encryption_service
from app.models import (
    Client,
    ConnectionStatus,
    PlatformConnection,
    UnifiedMetricCache,
)
from app.services.data_providers import get_data_provider
from app.services.normalization import normalize_platform_row

logger = logging.getLogger(__name__)


# ============================================================
# Sync SQLAlchemy engine + session factory for worker use
# ============================================================
# Built lazily on first task invocation so module import is cheap.

_sync_engine = None
_SyncSessionLocal = None


def _get_sync_session() -> Session:
    """Return a brand new synchronous SQLAlchemy session."""
    global _sync_engine, _SyncSessionLocal
    if _sync_engine is None:
        _sync_engine = create_engine(
            settings.sync_database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        _SyncSessionLocal = sessionmaker(
            bind=_sync_engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _SyncSessionLocal()


# ============================================================
# Helpers
# ============================================================

def _parse_metric_date(raw_value: Any) -> datetime | None:
    """
    Coerce a raw-row "metric_date" into a tz-aware datetime at UTC midnight.
    Accepts ISO strings ("2026-04-18"), date objects, and datetime objects.
    """
    if raw_value is None:
        return None
    if isinstance(raw_value, datetime):
        if raw_value.tzinfo is None:
            return raw_value.replace(tzinfo=timezone.utc)
        return raw_value.astimezone(timezone.utc)
    if isinstance(raw_value, date):
        return datetime.combine(raw_value, datetime.min.time(), tzinfo=timezone.utc)
    if isinstance(raw_value, str):
        try:
            parsed = datetime.fromisoformat(raw_value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            try:
                parsed_date = date.fromisoformat(raw_value)
                return datetime.combine(
                    parsed_date, datetime.min.time(), tzinfo=timezone.utc
                )
            except ValueError:
                return None
    return None


def _upsert_metric_rows(
    db: Session,
    client_id: UUID,
    connection: PlatformConnection,
    normalized_rows: List[Dict[str, Any]],
) -> int:
    """
    Write normalized metric rows to unified_metrics_cache.

    Strategy: delete-then-insert within the (client, platform, date, metric_name,
    campaign_id) space covered by this batch, so re-running a sync for the same
    window doesn't leave stale rows. This is simpler than a true PG UPSERT and
    plenty fast for Phase 2 volumes.
    """
    inserted = 0

    # Figure out the (metric_date, metric_name, campaign_id) triples we're about
    # to replace, so we can delete them first.
    # For small batches it's fine to just delete per-row.
    for row in normalized_rows:
        metric_date = _parse_metric_date(row.get("metric_date"))
        if metric_date is None:
            continue

        # Delete pre-existing row at this exact key (if any)
        db.query(UnifiedMetricCache).filter(
            UnifiedMetricCache.client_id == client_id,
            UnifiedMetricCache.platform_type == connection.platform_type,
            UnifiedMetricCache.metric_name == row["metric_name"],
            UnifiedMetricCache.metric_date == metric_date,
            UnifiedMetricCache.campaign_id == row.get("campaign_id"),
        ).delete(synchronize_session=False)

        new_row = UnifiedMetricCache(
            client_id=client_id,
            platform_type=connection.platform_type,
            metric_name=row["metric_name"],
            metric_value=float(row["metric_value"]),
            metric_date=metric_date,
            campaign_id=row.get("campaign_id"),
            campaign_name=row.get("campaign_name"),
            raw_json=row.get("raw_json"),
        )
        db.add(new_row)
        inserted += 1

    db.commit()
    return inserted


# ============================================================
# TASKS
# ============================================================

@shared_task(
    name="app.workers.sync_tasks.sync_client_metrics",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,   # up to 10 minutes between retries
    retry_jitter=True,
    max_retries=3,
)
def sync_client_metrics(self, client_id: str) -> Dict[str, Any]:
    """
    Fetch data for every ACTIVE connection on this client, normalize it,
    and upsert it into unified_metrics_cache.

    Window: [today - SYNC_LOOKBACK_DAYS .. today] in UTC.
    """
    client_uuid = UUID(client_id)
    today = date.today()
    start_date = today - timedelta(days=settings.SYNC_LOOKBACK_DAYS)

    logger.info(
        "[sync_client_metrics] client=%s window=%s→%s lookback=%d",
        client_uuid, start_date, today, settings.SYNC_LOOKBACK_DAYS,
    )

    provider = get_data_provider()
    encryption = get_encryption_service()

    summary = {
        "client_id": client_id,
        "provider": provider.name,
        "start_date": start_date.isoformat(),
        "end_date": today.isoformat(),
        "connections_processed": 0,
        "connections_failed": 0,
        "rows_written": 0,
    }

    db = _get_sync_session()
    try:
        # Confirm the client exists + is active
        client = db.query(Client).filter(Client.id == client_uuid).one_or_none()
        if client is None:
            logger.warning("[sync_client_metrics] client %s not found", client_uuid)
            return {**summary, "status": "client_not_found"}
        if not client.is_active:
            logger.info("[sync_client_metrics] client %s inactive, skipping", client_uuid)
            return {**summary, "status": "client_inactive"}

        # Fetch every connection (we'll only act on non-disconnected ones)
        connections = (
            db.query(PlatformConnection)
            .filter(PlatformConnection.client_id == client_uuid)
            .filter(PlatformConnection.status != ConnectionStatus.DISCONNECTED)
            .all()
        )

        for connection in connections:
            try:
                # Decrypt the credentials once, pass them to the provider.
                # Mock provider ignores them but the interface is consistent.
                credentials = encryption.decrypt_dict(connection.encrypted_credentials)

                raw_rows = provider.fetch_metrics(
                    connection=connection,
                    credentials=credentials,
                    start_date=start_date,
                    end_date=today,
                )

                # Unpivot: each raw row → many normalized metric rows
                normalized: List[Dict[str, Any]] = []
                for raw_row in raw_rows:
                    normalized.extend(
                        normalize_platform_row(connection.platform_type, raw_row)
                    )

                written = _upsert_metric_rows(
                    db=db,
                    client_id=client_uuid,
                    connection=connection,
                    normalized_rows=normalized,
                )

                # Update connection status — successful sync
                connection.status = ConnectionStatus.ACTIVE
                connection.last_synced_at = datetime.now(timezone.utc)
                connection.last_error_message = None
                db.commit()

                summary["connections_processed"] += 1
                summary["rows_written"] += written

                logger.info(
                    "[sync_client_metrics] connection %s platform=%s rows_written=%d",
                    connection.id, connection.platform_type.value, written,
                )

            except NotImplementedError as e:
                # Provider is a skeleton (windsor/supermetrics) — record and continue
                logger.warning(
                    "[sync_client_metrics] provider not implemented for %s: %s",
                    connection.platform_type.value, e,
                )
                summary["connections_failed"] += 1
                connection.status = ConnectionStatus.ERROR
                connection.last_error_message = str(e)[:500]
                db.commit()
            except Exception as e:
                logger.exception(
                    "[sync_client_metrics] connection %s failed: %s",
                    connection.id, e,
                )
                summary["connections_failed"] += 1
                connection.status = ConnectionStatus.ERROR
                connection.last_error_message = str(e)[:500]
                db.commit()

        return {**summary, "status": "ok"}

    finally:
        db.close()


@shared_task(name="app.workers.sync_tasks.sync_all_clients")
def sync_all_clients() -> Dict[str, Any]:
    """
    Iterate every active client across every agency, enqueue one
    sync_client_metrics task per client. This is the 3 AM UTC nightly job.

    We enqueue rather than run inline so the work fans out across multiple
    workers — one slow client's Meta rate-limit doesn't hold up others.
    """
    logger.info("[sync_all_clients] starting nightly fan-out")

    enqueued = 0
    db = _get_sync_session()
    try:
        active_client_ids = (
            db.execute(select(Client.id).where(Client.is_active.is_(True)))
            .scalars()
            .all()
        )

        for client_id in active_client_ids:
            sync_client_metrics.delay(str(client_id))
            enqueued += 1

        logger.info("[sync_all_clients] enqueued %d clients", enqueued)
        return {"enqueued": enqueued, "status": "ok"}
    finally:
        db.close()
