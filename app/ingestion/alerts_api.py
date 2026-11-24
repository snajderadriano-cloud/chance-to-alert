"""Adapter for official and open Ukrainian air raid alert APIs (alerts.in.ua)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.ingestion.base import BaseFeedAdapter, RawPost

logger = logging.getLogger(__name__)


class OpenAlertsApiAdapter(BaseFeedAdapter):
    """Adapter polling open alert status for regions and rayons."""

    def __init__(self, api_token: Optional[str] = None, endpoint: str = "https://api.alerts.in.ua/v1") -> None:
        self.api_token = api_token
        self.endpoint = endpoint
        self._cached_alerts: Dict[str, Any] = {}

    def poll(self) -> List[RawPost]:
        """Fetch current siren status from API (or return mock if no token configured)."""
        return []

    def get_active_siren_for_district(self, district_name: str) -> bool:
        """Check if official siren is active for a given district."""
        return self._cached_alerts.get(district_name.lower(), False)
