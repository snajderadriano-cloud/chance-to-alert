"""Integration tests for SQLite storage, deduplication, and SHA-256 audit chain."""

from datetime import datetime, timezone
import pytest
from app.domain.entities import ThreatSignal
from app.domain.enums import ThreatType
from app.storage.sqlite import SQLiteStorage


@pytest.fixture
def storage():
    db = SQLiteStorage(":memory:")
    yield db
    db.close()


class TestSQLiteStorage:
    def test_save_post_deduplication(self, storage):
        saved1 = storage.save_post("post-1", "chan-1", 100, "Текст повідомлення", "2026-11-23T12:00:00Z")
        assert saved1 is True

        # Exact duplicate
        saved2 = storage.save_post("post-1", "chan-1", 100, "Текст повідомлення", "2026-11-23T12:00:00Z")
        assert saved2 is False

    def test_save_post_revision_tracking(self, storage):
        storage.save_post("post-2", "chan-1", 101, "Початковий текст", "2026-11-23T12:00:00Z")
        # Edited post with same message_id
        updated = storage.save_post("post-2-edit", "chan-1", 101, "Оновлений текст з правками", "2026-11-23T12:01:00Z")
        assert updated is True

        cur = storage.conn.cursor()
        cur.execute("SELECT revision, text FROM posts WHERE channel = 'chan-1' AND message_id = 101")
        rev, text = cur.fetchone()
        assert rev == 2
        assert "Оновлений" in text

    def test_record_event_and_audit_chain_verification(self, storage):
        sig1 = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            quantity=3,
            raw_text="3 БПЛА курсом на Одесу",
            source_channel="vanek",
        )
        sig2 = ThreatSignal(
            threat_type=ThreatType.BALLISTIC,
            quantity=1,
            raw_text="Балістика з Криму",
            source_channel="alerts",
        )

        hash1 = storage.record_event(sig1)
        hash2 = storage.record_event(sig2)

        assert hash1 is not None and len(hash1) == 64
        assert hash2 is not None and len(hash2) == 64
        assert hash1 != hash2

        # Verify audit chain integrity
        assert storage.verify_audit_chain() is True

    def test_get_events_pagination(self, storage):
        for i in range(15):
            sig = ThreatSignal(
                threat_type=ThreatType.SHAHED,
                quantity=i + 1,
                raw_text=f"Повідомлення {i}",
                source_channel="test",
            )
            storage.record_event(sig)

        events_page1 = storage.get_events(limit=5, offset=0)
        assert len(events_page1) == 5

        events_page2 = storage.get_events(limit=5, offset=5)
        assert len(events_page2) == 5
        # Ensure pages are distinct
        page1_ids = {e["event_id"] for e in events_page1}
        page2_ids = {e["event_id"] for e in events_page2}
        assert page1_ids.isdisjoint(page2_ids)
