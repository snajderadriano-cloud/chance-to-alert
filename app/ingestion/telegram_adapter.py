"""Telegram channel ingestion adapter supporting live and webhook polling."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from app.config import ChannelConfig
from app.ingestion.base import BaseFeedAdapter, RawPost

logger = logging.getLogger(__name__)


class TelegramFeedAdapter(BaseFeedAdapter):
    """Adapter for connecting to Telegram channels via Bot API or MTProto."""

    def __init__(
        self,
        channels: Optional[List[ChannelConfig]] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        bot_token: Optional[str] = None,
    ) -> None:
        self.channels = channels or []
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self._queue: List[RawPost] = []
        self._is_connected = False

    def is_connected(self) -> bool:
        return self._is_connected

    def add_channel(self, channel: ChannelConfig) -> None:
        if channel not in self.channels:
            self.channels.append(channel)

    def enqueue_post(self, post: RawPost) -> None:
        """Push an incoming webhook/post into the ingestion queue."""
        self._queue.append(post)

    def poll(self) -> List[RawPost]:
        """Drain queued posts."""
        pulled = list(self._queue)
        self._queue.clear()
        return pulled
