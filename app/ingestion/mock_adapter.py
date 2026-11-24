"""Mock feed adapter for deterministic test replay and simulation."""

from __future__ import annotations

from typing import List, Optional

from app.ingestion.base import BaseFeedAdapter, RawPost


class MockFeedAdapter(BaseFeedAdapter):
    """Replays deterministic raw post sequences for testing."""

    def __init__(self, posts: Optional[List[RawPost]] = None) -> None:
        self.posts: List[RawPost] = list(posts or [])
        self._cursor: int = 0

    def add_post(self, post: RawPost) -> None:
        self.posts.append(post)

    def poll(self) -> List[RawPost]:
        items: List[RawPost] = []
        while self._cursor < len(self.posts):
            items.append(self.posts[self._cursor])
            self._cursor += 1
        return items

    def get_next(self) -> Optional[RawPost]:
        if self._cursor < len(self.posts):
            p = self.posts[self._cursor]
            self._cursor += 1
            return p
        return None

    def reset(self) -> None:
        self._cursor = 0
