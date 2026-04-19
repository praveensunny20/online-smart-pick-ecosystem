"""
Celery application instance.

Launch a worker with:
    celery -A app.workers.celery_app worker --loglevel=info

Launch beat (the scheduler) with:
    celery -A app.workers.celery_app beat --loglevel=info

Both processes pick up tasks from app.workers.sync_tasks automatically because
we call `autodiscover_tasks(["app.workers"])` below.
"""
from __future__ import annotations

from celery import Celery

from app.core.config import settings
from app.workers.beat_schedule import beat_schedule

# Instantiate the Celery app. The first positional arg is the main module name,
# used for generating task IDs — "smartpick" is a tidy prefix.
celery_app = Celery(
    "smartpick",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.sync_tasks"],
)

# Global Celery configuration
celery_app.conf.update(
    # Timezone — store task timestamps in UTC, always
    timezone="UTC",
    enable_utc=True,
    # Serialization — JSON is the safest default
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Keep task results for 24h then expire them from Redis
    result_expires=60 * 60 * 24,
    # A task that's been running for 30 minutes is almost certainly hung
    task_time_limit=30 * 60,
    # Soft limit — task gets a SoftTimeLimitExceeded exception so it can clean up
    task_soft_time_limit=25 * 60,
    # Don't prefetch lots of tasks per worker; sync tasks are slow and we'd
    # rather the broker redistribute work across workers.
    worker_prefetch_multiplier=1,
    # Acknowledge tasks AFTER they've completed, so a worker crash retries them
    task_acks_late=True,
    # Beat schedule (3 AM nightly sync, etc.)
    beat_schedule=beat_schedule,
)

# Pick up any @shared_task or @celery_app.task decorated functions in
# app.workers.* at worker boot time.
celery_app.autodiscover_tasks(["app.workers"])
