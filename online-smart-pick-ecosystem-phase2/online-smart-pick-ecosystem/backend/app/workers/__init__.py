"""
Celery workers package.

Contains:
    celery_app     — The Celery() instance. Workers launch with:
                     `celery -A app.workers.celery_app worker`
    sync_tasks     — Tasks that fetch + normalize + upsert platform metrics.
    beat_schedule  — The 3 AM nightly schedule for sync_all_clients.
"""
