"""Abstract interface for threat data storage and audit trail."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.domain.entities import ThreatSignal


class ThreatRepository(ABC):
    """Abstract interface for post persistence and threat event auditing."""

    @abstractmethod
    def save_post(self, post_id: str, channel: str, message_id: int, text: str, timestamp_iso: str) -> bool:
        """Save a post with deduplication. Returns True if saved or updated, False if duplicate."""
        pass

    @abstractmethod
    def record_event(self, signal: ThreatSignal) -> str:
        """Record a threat event and append to audit chain. Returns entry hash."""
        pass

    @abstractmethod
    def get_events(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve recent threat events with pagination."""
        pass

    @abstractmethod
    def verify_audit_chain(self) -> bool:
        """Verify cryptographic integrity of audit chain."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
        pass
