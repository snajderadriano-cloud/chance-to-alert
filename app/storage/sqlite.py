"""SQLite implementation with content deduplication, revisions, and SHA-256 audit chain."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.domain.entities import ThreatSignal
from app.storage.base import ThreatRepository


class SQLiteStorage(ThreatRepository):
    """Hermetic SQLite storage with message deduplication, revision history, and SHA-256 audit chain."""

    def __init__(self, db_path: Union[str, Path] = ":memory:") -> None:
        self.db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_conn()
        self._init_db()

    def _ensure_conn(self) -> sqlite3.Connection:
        need_init = False
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            need_init = True
        else:
            try:
                self._conn.execute("SELECT 1")
            except Exception:
                self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
                need_init = True
        if need_init:
            self._init_db()
        return self._conn

    @property
    def conn(self) -> sqlite3.Connection:
        return self._ensure_conn()

    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    content_hash TEXT UNIQUE NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    timestamp TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS threat_events (
                    event_id TEXT PRIMARY KEY,
                    threat_type TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    raw_text TEXT NOT NULL,
                    source_channel TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    index_num INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS channel_performance (
                    channel TEXT PRIMARY KEY,
                    total_signals INTEGER NOT NULL DEFAULT 0,
                    confirmed_signals INTEGER NOT NULL DEFAULT 0,
                    unconfirmed_signals INTEGER NOT NULL DEFAULT 0,
                    total_lead_time_minutes REAL NOT NULL DEFAULT 0.0,
                    calibrated_weight REAL NOT NULL DEFAULT 0.85,
                    last_updated TEXT NOT NULL
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS corridor_hourly_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hour_of_day INTEGER NOT NULL,
                    corridor_name TEXT NOT NULL,
                    threat_type TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    last_observed TEXT NOT NULL,
                    UNIQUE(hour_of_day, corridor_name, threat_type)
                )
            """)

    def save_post(self, post_id: str, channel: str, message_id: int, text: str, timestamp_iso: str) -> bool:
        """Save a raw post with deduplication by content hash."""
        data = f"{channel}:{post_id}:{text}"
        content_hash = hashlib.sha256(data.encode("utf-8")).hexdigest()

        cur = self.conn.cursor()
        cur.execute("SELECT id FROM posts WHERE content_hash = ?", (content_hash,))
        if cur.fetchone():
            return False  # Duplicate

        cur.execute("SELECT id, revision FROM posts WHERE channel = ? AND message_id = ?", (channel, message_id))
        row = cur.fetchone()
        now_iso = datetime.now(timezone.utc).isoformat()
        if row:
            existing_id, current_rev = row
            new_rev = current_rev + 1
            with self.conn:
                self.conn.execute(
                    "UPDATE posts SET text = ?, content_hash = ?, revision = ?, timestamp = ? WHERE id = ?",
                    (text, content_hash, new_rev, timestamp_iso, existing_id),
                )
                self.conn.execute(
                    "INSERT INTO revisions (post_id, revision, text, timestamp) VALUES (?, ?, ?, ?)",
                    (existing_id, new_rev, text, timestamp_iso),
                )
            return True

        with self.conn:
            self.conn.execute(
                "INSERT INTO posts (id, channel, message_id, text, content_hash, revision, timestamp, created_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (post_id, channel, message_id, text, content_hash, timestamp_iso, now_iso),
            )
            self.conn.execute(
                "INSERT INTO revisions (post_id, revision, text, timestamp) VALUES (?, 1, ?, ?)",
                (post_id, text, timestamp_iso),
            )
        return True

    def record_event(self, signal: ThreatSignal) -> str:
        """Record a threat event and append to the SHA-256 cryptographic audit chain."""
        now_iso = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO threat_events (event_id, threat_type, quantity, raw_text, source_channel, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (signal.threat_id, signal.threat_type.value, signal.quantity, signal.raw_text, signal.source_channel, signal.timestamp.isoformat()),
            )

        cur.execute("SELECT entry_hash FROM audit_log ORDER BY index_num DESC LIMIT 1")
        last_row = cur.fetchone()
        prev_hash = last_row[0] if last_row else ("0" * 64)

        payload = json.dumps(signal.to_dict(), sort_keys=True)
        entry_hash = hashlib.sha256(f"{prev_hash}:{payload}:{now_iso}".encode("utf-8")).hexdigest()

        with self.conn:
            self.conn.execute(
                "INSERT INTO audit_log (event_id, previous_hash, entry_hash, payload, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (signal.threat_id, prev_hash, entry_hash, payload, now_iso),
            )
        return entry_hash

    def get_events(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve threat events with pagination."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT event_id, threat_type, quantity, raw_text, source_channel, timestamp "
            "FROM threat_events ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (max(1, limit), max(0, offset)),
        )
        rows = cur.fetchall()
        return [
            {
                "event_id": r[0],
                "threat_type": r[1],
                "quantity": r[2],
                "raw_text": r[3],
                "source_channel": r[4],
                "timestamp": r[5],
            }
            for r in rows
        ]

    def verify_audit_chain(self) -> bool:
        """Verify cryptographic integrity of the SHA-256 audit chain."""
        cur = self.conn.cursor()
        cur.execute("SELECT index_num, previous_hash, entry_hash, payload, created_at FROM audit_log ORDER BY index_num ASC")
        rows = cur.fetchall()
        if not rows:
            return True

        expected_prev = "0" * 64
        for row in rows:
            idx, prev_h, entry_h, payload, created_at = row
            if prev_h != expected_prev:
                return False
            computed = hashlib.sha256(f"{prev_h}:{payload}:{created_at}".encode("utf-8")).hexdigest()
            if computed != entry_h:
                return False
            expected_prev = entry_h
        return True

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
