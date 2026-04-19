"""
Data provider factory.

Reads `settings.DATA_PROVIDER` and returns the matching provider class instance.
Keeps the rest of the app decoupled from whichever integration we use —
the Celery sync task just calls `get_data_provider().fetch_metrics(...)`.

Options:
    "mock"         → MockProvider (default, works offline with deterministic data)
    "windsor"      → WindsorProvider (Phase 3 — real API integration)
    "supermetrics" → SupermetricsProvider (Phase 3 — real API integration)
"""
from __future__ import annotations

from app.core.config import settings
from app.services.data_providers.base import BaseProvider
from app.services.data_providers.mock import MockProvider
from app.services.data_providers.supermetrics import SupermetricsProvider
from app.services.data_providers.windsor import WindsorProvider


def get_data_provider() -> BaseProvider:
    """Return the provider instance configured in .env."""
    choice = (settings.DATA_PROVIDER or "mock").strip().lower()

    if choice == "mock":
        return MockProvider()
    if choice == "windsor":
        return WindsorProvider()
    if choice == "supermetrics":
        return SupermetricsProvider()

    # Unknown value → fall back to mock so the app still boots. The sync task
    # will log a warning when it sees this.
    return MockProvider()


__all__ = [
    "BaseProvider",
    "MockProvider",
    "WindsorProvider",
    "SupermetricsProvider",
    "get_data_provider",
]
