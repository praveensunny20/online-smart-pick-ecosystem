"""
Health check endpoints.

Used by Docker, load balancers, and monitoring systems to know if the app is alive.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Liveness check")
async def health():
    """Basic liveness check — does the process respond?"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
    }


@router.get("/db", summary="Database readiness check")
async def health_db(db: AsyncSession = Depends(get_db)):
    """
    Readiness check — can the app talk to Postgres?
    Returns 200 if the DB responds to `SELECT 1`, 503 otherwise.
    """
    try:
        result = await db.execute(text("SELECT 1"))
        value = result.scalar()
        if value != 1:
            return {"status": "error", "detail": "unexpected result"}, status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "ok", "database": "reachable"}
    except Exception as e:
        return (
            {"status": "error", "detail": str(e)},
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
