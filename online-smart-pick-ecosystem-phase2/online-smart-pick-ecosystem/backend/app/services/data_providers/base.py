"""
Abstract base class that all data providers must implement.

Every provider (Mock, Windsor, Supermetrics) is given a PlatformConnection
row (which knows the platform_type, plus the decrypted credentials), a start
date, and an end date. It must return a list of dicts in the "raw row" shape
expected by `app.services.normalization.normalize_platform_row`.

Expected return shape (per row):
    {
        "date": "2026-04-18",
        "campaign_id": "123",             # optional
        "campaign_name": "Spring Sale",   # optional
        # any number of platform-specific metric fields:
        "impressions": 1200,
        "clicks": 45,
        "spend": 8.75,
        ...
    }
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List

from app.models import PlatformConnection


class BaseProvider(ABC):
    """Every concrete provider subclasses this."""

    #: Human-readable name — used in logs and error messages.
    name: str = "base"

    @abstractmethod
    def fetch_metrics(
        self,
        connection: PlatformConnection,
        credentials: Dict[str, Any],
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Fetch raw metric rows for the given platform connection and date range.

        Args:
            connection: The PlatformConnection ORM row (read-only access to
                platform_type, account_name, client_id, etc.)
            credentials: The decrypted credentials dict. Providers should
                never call connection.encrypted_credentials themselves —
                decryption happens once in the caller.
            start_date: Inclusive start of date range (UTC date).
            end_date:   Inclusive end of date range (UTC date).

        Returns:
            List of raw rows (see module docstring for shape).
        """
        raise NotImplementedError
