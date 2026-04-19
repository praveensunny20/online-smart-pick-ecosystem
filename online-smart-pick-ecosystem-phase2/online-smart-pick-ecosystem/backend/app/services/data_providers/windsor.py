"""
Windsor.ai provider — SKELETON.

Windsor.ai exposes a REST API that can pull data from every major platform
through their single hosted connector, which is why it's attractive for this
project. In Phase 3 we'll implement:

    - /connectors/{name}/fields discovery
    - /connectors/{name}/data with the account_id and date range
    - auth via X-API-Key header from settings.WINDSOR_API_KEY

For now, this class raises NotImplementedError so that if someone flips
settings.DATA_PROVIDER to "windsor" before Phase 3, the error message
is clear.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from app.models import PlatformConnection
from app.services.data_providers.base import BaseProvider


class WindsorProvider(BaseProvider):
    name = "windsor"

    def fetch_metrics(
        self,
        connection: PlatformConnection,
        credentials: Dict[str, Any],
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "Windsor.ai provider is wired in Phase 3. "
            "Set DATA_PROVIDER=mock in .env for now."
        )
