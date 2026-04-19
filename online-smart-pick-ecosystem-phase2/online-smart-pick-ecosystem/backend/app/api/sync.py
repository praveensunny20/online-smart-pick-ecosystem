"""
Sync API routes.

    POST /data/sync/{client_id}   — Manual trigger. Enqueues a Celery task
                                     that re-fetches data for every active
                                     platform connection on this client.

The actual fetch-and-normalize logic lives in app.workers.sync_tasks. This
endpoint is just a thin wrapper so the frontend can kick off a refresh on
demand (e.g. user clicks "Refresh data" in the UI).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_manager
from app.db.session import get_db
from app.models import AgencyUser, Client
from app.schemas.metrics import SyncTriggerResponse

router = APIRouter(prefix="/data", tags=["data-sync"])


@router.post(
    "/sync/{client_id}",
    response_model=SyncTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually trigger a data sync for a client (enqueues Celery task)",
)
async def trigger_sync(
    client_id: UUID,
    current_user: AgencyUser = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify the client belongs to the caller's agency, then enqueue a
    sync_client_metrics Celery task.

    Note: the Celery import happens inside the function so that unit tests
    and docs generation don't need Redis to be running.
    """
    # Ownership check (RLS would also catch this, but we prefer a clean 404)
    result = await db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.agency_id == current_user.agency_id,
        )
    )
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")

    try:
        from app.workers.sync_tasks import sync_client_metrics  # noqa: WPS433
    except Exception as e:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=503,
            detail=f"Worker subsystem unavailable: {e}",
        )

    async_result = sync_client_metrics.delay(str(client_id))

    return SyncTriggerResponse(
        client_id=client_id,
        task_id=async_result.id,
        status="queued",
        message=(
            "Sync task queued. Check Celery worker logs to follow progress, "
            "or poll GET /clients/{id}/metrics to see results as they land."
        ),
    )
