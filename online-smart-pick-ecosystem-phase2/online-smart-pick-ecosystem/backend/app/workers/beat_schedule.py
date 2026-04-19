"""
Celery Beat schedule.

Separated from celery_app.py so sync_tasks.py can import it without creating
a circular import (celery_app imports sync_tasks, sync_tasks would otherwise
have to import celery_app for the schedule dict).
"""
from __future__ import annotations

from celery.schedules import crontab

from app.core.config import settings


beat_schedule = {
    # Nightly 3 AM UTC — iterate every active client, enqueue a sync per client.
    "nightly-sync-all-clients": {
        "task": "app.workers.sync_tasks.sync_all_clients",
        "schedule": crontab(
            hour=str(settings.SYNC_SCHEDULE_HOUR_UTC),
            minute=str(settings.SYNC_SCHEDULE_MINUTE),
        ),
        # Name that shows up in beat logs
        "options": {"expires": 60 * 60},  # drop if not picked up within 1h
    },
}
