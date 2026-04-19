"""
Supermetrics provider — SKELETON.

Supermetrics is the 800-lb gorilla of marketing-data connectors and is the
direct competitor we're benchmarking against. In Phase 3 we'll implement:

    - The Supermetrics MCP / REST API calls (data_source_discovery,
      field_discovery, data_query)
    - Auth via the API key in settings.SUPERMETRICS_API_KEY
    - Mapping each PlatformType to the right Supermetrics data source id
      (e.g. PlatformType.META_ADS → "FBADS")

For Phase 2 we ship only the skeleton so that flipping settings.DATA_PROVIDER
to "supermetrics" fails loudly instead of silently.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from app.models import PlatformConnection
from app.services.data_providers.base import BaseProvider


class SupermetricsProvider(BaseProvider):
    name = "supermetrics"

    def fetch_metrics(
        self,
        connection: PlatformConnection,
        credentials: Dict[str, Any],
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "Supermetrics provider is wired in Phase 3. "
            "Set DATA_PROVIDER=mock in .env for now."
        )
