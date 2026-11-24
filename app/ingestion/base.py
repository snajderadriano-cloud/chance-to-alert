"""Base abstractions for threat feeds and ingested posts."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class RawPost:
    """Normalized ingested Telegram post."""

    id: str
    channel: str
    text: str
    timestamp: datetime
    message_id: int = 1
    media: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)

    @property
    def content_hash(self) -> str:
        data = f"{self.channel}:{self.id}:{self.text}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "channel": self.channel,
            "text": self.text,
            "timestamp": self.timestamp.isoformat(),
            "message_id": self.message_id,
            "media": self.media,
            "metadata": dict(self.metadata),
        }


class BaseFeedAdapter(ABC):
    """Abstract interface for threat post feeds."""

    @abstractmethod
    def poll(self) -> List[RawPost]:
        """Poll new posts from the feed."""
        pass
