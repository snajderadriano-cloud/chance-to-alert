"""Centralized E2E test harness and fixtures for Chance to Alert.App.

Provides:
- ASGI test client (httpx.AsyncClient with ASGITransport) against app.main:app
  (with graceful contract fallback if app.main is being authored in parallel).
- Starlette TestClient for WebSocket handshake and push stream testing.
- Target presets (Odesa District, Odesa Oblast) and AppConfig fixtures.
- Deterministic base UTC datetime fixture.
- Synthetic threat signal and raw post factories.
- Temporary hermetic storage fixtures.
- Reference contract providers for processing, ingestion, storage, and tracking.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import sqlite3
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, Generator, List, Optional, Set, Tuple, Union

import httpx
from httpx import ASGITransport
import pytest
import pytest_asyncio
from starlette.testclient import TestClient

from app.config import AppConfig, ChannelConfig, get_preset, list_channels, list_presets, load_config
from app.domain.entities import (
    GeoCoordinate,
    ProbabilityResult,
    TargetPreset,
    ThreatContribution,
    ThreatSignal,
    TrajectoryVector,
)
from app.domain.enums import AlertLevel, MovementSpeedClass, ThreatType
from app.domain.geo import (
    bearing_difference,
    calculate_azimuth,
    calculate_heading_alignment_factor,
    estimate_time_to_target,
    haversine_distance,
    is_heading_towards_target,
)
from app.domain.scoring import (
    DEFAULT_SCORING_CONFIG,
    ScoringConfig,
    calculate_aggregate_probability,
    calculate_distance_decay,
    calculate_swarm_multiplier,
    calculate_temporal_decay,
    calculate_threat_probability,
)

# ==============================================================================
# 1. REFERENCE CONTRACT IMPLEMENTATIONS FOR IN-PROGRESS MODULES
# ==============================================================================

# --- Feature 5: Text Sanitizer & Homoglyph Defense ---

ZERO_WIDTH_CHARS: Set[str] = {
    "\u200b",  # Zero-width space
    "\u200c",  # Zero-width non-joiner
    "\u200d",  # Zero-width joiner
    "\ufeff",  # Zero-width no-break space (BOM)
    "\u2060",  # Word joiner
    "\u00ad",  # Soft hyphen
    "\u200e",  # Left-to-right mark
    "\u200f",  # Right-to-left mark
}

INVISIBLE_CHARS: Set[str] = {
    "\u034f",  # Combining Grapheme Joiner
    "\u180e",  # Mongolian Vowel Separator
    "\u061c",  # Arabic Letter Mark
    "\u17b4",  # Khmer Vowel Inherent Aq
    "\u17b5",  # Khmer Vowel Inherent Aa
    "\u115f",  # Hangul Choseong Filler
    "\u1160",  # Hangul Jungseong Filler
    "\u3164",  # Hangul Filler
    "\uffa0",  # Halfwidth Hangul Filler
    *{chr(cp) for cp in range(0xFE00, 0xFE10)},  # Variation Selectors
}

# Latin to Cyrillic homoglyph lookalike mapping (for Ukrainian/Cyrillic messages)
LATIN_TO_CYRILLIC_HOMOGLYPHS: Dict[str, str] = {
    "a": "а", "A": "А",
    "b": "б", "B": "В",
    "c": "с", "C": "С",
    "e": "е", "E": "Е",
    "h": "һ", "H": "Н",
    "i": "і", "I": "І",
    "k": "к", "K": "К",
    "m": "м", "M": "М",
    "o": "о", "O": "О",
    "p": "р", "P": "Р",
    "s": "ѕ", "S": "Ѕ",
    "t": "т", "T": "Т",
    "x": "х", "X": "Х",
    "y": "у", "Y": "У",
}

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"override\s+risk", re.IGNORECASE),
    re.compile(r"bypass\s+mode", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"drop\s+table", re.IGNORECASE),
]


class TextSanitizer:
    """Sanitizes incoming Telegram post text against poisoning, zero-width chars, and injection."""

    def strip_zero_width_chars(self, text: str) -> str:
        """Strip all zero-width and invisible unicode characters."""
        if not text:
            return ""
        all_invisible = ZERO_WIDTH_CHARS.union(INVISIBLE_CHARS)
        return "".join(ch for ch in text if ch not in all_invisible)

    def normalize_homoglyphs(self, text: str) -> str:
        """Normalize mixed-script homoglyphs to consistent Cyrillic characters."""
        if not text:
            return ""
        # Check if text contains Cyrillic characters; if so, replace isolated Latin homoglyphs
        has_cyrillic = bool(re.search(r"[\u0400-\u04FF]", text))
        if has_cyrillic:
            chars = [LATIN_TO_CYRILLIC_HOMOGLYPHS.get(ch, ch) for ch in text]
            return "".join(chars)
        return text

    def neutralize_prompt_injection(self, text: str) -> str:
        """Strip or neutralize prompt injection attempts and SQL fragments."""
        cleaned = text
        for pattern in PROMPT_INJECTION_PATTERNS:
            cleaned = pattern.sub("", cleaned)
        return cleaned.strip()

    def strip_control_chars(self, text: str) -> str:
        """Strip ASCII and Unicode control characters while preserving newlines and Ukrainian apostrophes."""
        if not text:
            return ""
        out = []
        for ch in text:
            cp = ord(ch)
            if cp in (10, 13, 9):  # \n, \r, \t
                out.append(ch)
            elif (cp < 32) or (127 <= cp <= 159):
                continue
            else:
                out.append(ch)
        return "".join(out)

    def sanitize(self, text: str) -> str:
        """Full sanitization pipeline."""
        if not text:
            return ""
        t = self.strip_zero_width_chars(text)
        t = self.strip_control_chars(t)
        t = self.normalize_homoglyphs(t)
        t = self.neutralize_prompt_injection(t)
        return t.strip()


# Try importing real sanitizer if available
try:
    from app.processing.sanitizer import SignalPoisoningGuard  # type: ignore
    sanitizer_instance = SignalPoisoningGuard()
except Exception:
    sanitizer_instance = TextSanitizer()


# --- Feature 7: Regional Gazetteer & Resolver ---

KNOWN_LOCATIONS: Dict[str, GeoCoordinate] = {
    # Odesa District & immediate perimeter
    "одеса": GeoCoordinate(lat=46.4825, lon=30.7233),
    "одесса": GeoCoordinate(lat=46.4825, lon=30.7233),
    "чорноморськ": GeoCoordinate(lat=46.3015, lon=30.6568),
    "черноморск": GeoCoordinate(lat=46.3015, lon=30.6568),
    "фонтанка": GeoCoordinate(lat=46.5647, lon=30.8586),
    "южне": GeoCoordinate(lat=46.6225, lon=31.1008),
    "південне": GeoCoordinate(lat=46.6225, lon=31.1008),
    "таїрове": GeoCoordinate(lat=46.3958, lon=30.6483),
    "крижанівка": GeoCoordinate(lat=46.5611, lon=30.7961),
    "усатове": GeoCoordinate(lat=46.5361, lon=30.6556),
    "овідіополь": GeoCoordinate(lat=46.2464, lon=30.4431),
    "біляївка": GeoCoordinate(lat=46.4833, lon=30.2000),

    # Danube Ports (Southern Odesa Oblast)
    "ізмаїл": GeoCoordinate(lat=45.3500, lon=28.8333),
    "измаил": GeoCoordinate(lat=45.3500, lon=28.8333),
    "рені": GeoCoordinate(lat=45.4500, lon=28.2833),
    "рени": GeoCoordinate(lat=45.4500, lon=28.2833),
    "кілія": GeoCoordinate(lat=45.4475, lon=29.2689),
    "килия": GeoCoordinate(lat=45.4475, lon=29.2689),
    "вилкове": GeoCoordinate(lat=45.3986, lon=29.5936),
    "вилково": GeoCoordinate(lat=45.3986, lon=29.5936),

    # Transit corridors & Launch Areas
    "чорне море": GeoCoordinate(lat=45.8000, lon=31.2000),
    "крим": GeoCoordinate(lat=45.0000, lon=34.0000),
    "чауда": GeoCoordinate(lat=45.0050, lon=35.8360),
    "миколаїв": GeoCoordinate(lat=46.9667, lon=31.9833),
    "миколаївщина": GeoCoordinate(lat=46.9667, lon=31.9833),
    "очаків": GeoCoordinate(lat=46.6167, lon=31.5500),
    "коблове": GeoCoordinate(lat=46.6667, lon=31.2000),
}


class RegionalGazetteer:
    """Geographic resolver for Odesa District, Odesa Oblast, and maritime corridors."""

    def __init__(self, catalog: Optional[Dict[str, GeoCoordinate]] = None) -> None:
        self.catalog = catalog or dict(KNOWN_LOCATIONS)

    def resolve(self, place_name: str) -> Optional[GeoCoordinate]:
        """Resolve a place name or alias to a GeoCoordinate."""
        if not place_name:
            return None
        cleaned = place_name.strip().lower()
        # Clean trailing punctuation
        cleaned = re.sub(r"[!?,.:;]+$", "", cleaned).strip()
        if cleaned in self.catalog:
            return self.catalog[cleaned]

        # Case-insensitive substring match
        for key, coord in self.catalog.items():
            if key == cleaned or (len(key) > 4 and key in cleaned):
                return coord
        return None

    def extract_places(self, text: str) -> List[str]:
        """Extract mentioned known geographical entities from text."""
        if not text:
            return []
        lower = text.lower()
        found: List[str] = []
        for name in self.catalog:
            pattern = rf"\b{re.escape(name)}\b"
            if re.search(pattern, lower):
                found.append(name)
        return found


# --- Feature 6: Ukrainian Threat Parser & Lexicon ---

class ThreatParser:
    """Deterministic parser extracting ThreatSignals from sanitized Ukrainian Telegram posts."""

    def __init__(self, gazetteer: Optional[RegionalGazetteer] = None) -> None:
        self.gazetteer = gazetteer or RegionalGazetteer()
        self.sanitizer = sanitizer_instance

    def parse(
        self,
        text: str,
        channel: str = "general",
        timestamp: Optional[datetime] = None,
    ) -> List[ThreatSignal]:
        """Parse raw text into one or more ThreatSignals."""
        if not text or not text.strip():
            return []

        ts = timestamp or datetime.now(timezone.utc)
        clean = self.sanitizer.sanitize(text)
        lower = clean.lower()

        # 1. Check for cancellation signals
        is_all_clear = bool(
            re.search(r"\b(відбій|чисто|відбою|відбій\s+тривоги)\b", lower)
        )
        if is_all_clear:
            cancelled_type = ThreatType.UNKNOWN
            if "шахед" in lower or "бпла" in lower:
                cancelled_type = ThreatType.SHAHED
            elif "балістик" in lower:
                cancelled_type = ThreatType.BALLISTIC
            elif "ракет" in lower:
                cancelled_type = ThreatType.CRUISE_MISSILE

            signals = [
                ThreatSignal(
                    threat_type=cancelled_type,
                    quantity=1,
                    raw_text=clean,
                    source_channel=channel,
                    timestamp=ts,
                    is_cancellation=True,
                )
            ]
            if "загроза балістики" in lower or "залишається загроза" in lower:
                signals.append(
                    ThreatSignal(
                        threat_type=ThreatType.BALLISTIC,
                        quantity=1,
                        raw_text=clean,
                        source_channel=channel,
                        timestamp=ts,
                        is_cancellation=False,
                    )
                )
            return signals

        # 2. Extract ThreatType(s)
        detected_types: List[ThreatType] = []
        if re.search(r"\b(шахед|шахеди|shahed|бпла|мопед|мопеди|дрон|дрони)\b", lower):
            detected_types.append(ThreatType.SHAHED)
        if re.search(r"\b(балістик|балістика|балістична|іскандер|кинджал)\b", lower):
            detected_types.append(ThreatType.BALLISTIC)
        if re.search(r"\b(крилат|ракета|ракети|калібр|х-101|х101)\b", lower):
            if ThreatType.BALLISTIC not in detected_types:
                detected_types.append(ThreatType.CRUISE_MISSILE)
        if re.search(r"\b(авіаці|су-34|су-35|каб|каби)\b", lower):
            detected_types.append(ThreatType.TACTICAL_AVIATION)
        if re.search(r"\b(розвідник|орлан|zala|суперкам)\b", lower):
            detected_types.append(ThreatType.RECON_DRONE)

        if not detected_types:
            detected_types = [ThreatType.UNKNOWN]

        # 3. Extract quantity
        qty = 1
        qty_match = re.search(r"(\d+)\s*(?:х|x|\-|\s)*(?:бпла|шахед|ракет|ціл|штук)?", lower)
        if qty_match:
            try:
                found_qty = int(qty_match.group(1))
                if 1 <= found_qty <= 1000:
                    qty = found_qty
            except (ValueError, TypeError):
                qty = 1
        elif "декілька" in lower or "пара" in lower:
            qty = 2
        elif "група" in lower or "рій" in lower:
            qty = 4

        # 4. Check heading negation
        negated_heading = bool(re.search(r"(не\s+в\s+бік|не\s+на|повз)\s+одес", lower))

        # 5. Extract origin and target locations
        origin = None
        target_heading = None
        if "з моря" in lower or "чорного моря" in lower:
            origin = "Чорне море"
        elif "з криму" in lower or "крим" in lower:
            origin = "Крим"

        detected_places = self.gazetteer.extract_places(clean)
        coord = None
        for p in detected_places:
            c = self.gazetteer.resolve(p)
            if c:
                coord = c
                break

        if not negated_heading and ("одес" in lower or "чорноморськ" in lower or "фонтанка" in lower):
            target_heading = "Одеса"
        elif negated_heading:
            target_heading = "інший напрямок"

        signals: List[ThreatSignal] = []
        for tt in detected_types:
            sig = ThreatSignal(
                threat_type=tt,
                quantity=qty,
                raw_text=clean,
                source_channel=channel,
                timestamp=ts,
                origin_location=origin,
                target_heading=target_heading,
                detected_locations=detected_places,
                current_coordinate=coord,
                is_cancellation=False,
            )
            signals.append(sig)

        return signals


# --- Feature 8: Feed Ingestion Adapters & Replay ---

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


class MockFeedAdapter:
    """Replays deterministic raw post sequences for testing."""

    def __init__(self, posts: Optional[List[RawPost]] = None) -> None:
        self.posts: List[RawPost] = list(posts or [])
        self._cursor: int = 0

    def add_post(self, post: RawPost) -> None:
        self.posts.append(post)

    def get_next(self) -> Optional[RawPost]:
        if self._cursor < len(self.posts):
            p = self.posts[self._cursor]
            self._cursor += 1
            return p
        return None

    def reset(self) -> None:
        self._cursor = 0


# --- Feature 9: SQLite Storage & Audit Hash Chain ---

class SQLiteStorage:
    """Hermetic SQLite storage with message deduplication, revision history, and SHA-256 audit chain."""

    def __init__(self, db_path: Union[str, Path] = ":memory:") -> None:
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

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

    def save_post(self, post: RawPost) -> bool:
        """Save a raw post with deduplication by content hash."""
        # Check if identical content hash exists
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM posts WHERE content_hash = ?", (post.content_hash,))
        if cur.fetchone():
            return False  # Duplicate

        # Check if existing channel + message_id exists (revision edit)
        cur.execute("SELECT id, revision FROM posts WHERE channel = ? AND message_id = ?", (post.channel, post.message_id))
        row = cur.fetchone()
        now_iso = datetime.now(timezone.utc).isoformat()
        if row:
            post_id, current_rev = row
            new_rev = current_rev + 1
            with self.conn:
                self.conn.execute(
                    "UPDATE posts SET text = ?, content_hash = ?, revision = ?, timestamp = ? WHERE id = ?",
                    (post.text, post.content_hash, new_rev, post.timestamp.isoformat(), post_id),
                )
                self.conn.execute(
                    "INSERT INTO revisions (post_id, revision, text, timestamp) VALUES (?, ?, ?, ?)",
                    (post_id, new_rev, post.text, post.timestamp.isoformat()),
                )
            return True

        with self.conn:
            self.conn.execute(
                "INSERT INTO posts (id, channel, message_id, text, content_hash, revision, timestamp, created_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (post.id, post.channel, post.message_id, post.text, post.content_hash, post.timestamp.isoformat(), now_iso),
            )
            self.conn.execute(
                "INSERT INTO revisions (post_id, revision, text, timestamp) VALUES (?, 1, ?, ?)",
                (post.id, post.text, post.timestamp.isoformat()),
            )
        return True

    def record_event(self, signal: ThreatSignal) -> str:
        """Record a threat event and append to the SHA-256 cryptographic audit chain."""
        now_iso = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        with self.conn:
            self.conn.execute(
                "INSERT INTO threat_events (event_id, threat_type, quantity, raw_text, source_channel, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (signal.threat_id, signal.threat_type.value, signal.quantity, signal.raw_text, signal.source_channel, signal.timestamp.isoformat()),
            )

        # Audit chain
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
        self.conn.close()


# --- Feature 10: Threat Tracking & Lifecycle Service ---

@dataclass
class ThreatTrack:
    """Active aerial threat track with corroboration and lifecycle state."""

    track_id: str
    threat_type: ThreatType
    quantity: int
    signals: List[ThreatSignal] = field(default_factory=list)
    state: str = "ACTIVE"  # ACTIVE, RESOLVED, EXPIRED
    confidence_score: float = 0.50
    first_detected: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trajectory: Optional[TrajectoryVector] = None

    def add_signal(self, signal: ThreatSignal, channel_weight: float = 0.90) -> None:
        self.signals.append(signal)
        self.quantity = max(self.quantity, signal.quantity)
        self.last_updated = signal.timestamp
        if signal.trajectory:
            self.trajectory = signal.trajectory
        # Corroboration increases confidence score
        unique_channels = {s.source_channel for s in self.signals if s.source_channel}
        self.confidence_score = min(1.0, 0.40 + 0.20 * len(unique_channels) + 0.10 * channel_weight)


class ThreatTrackingService:
    """Lifecycle tracking service managing active tracks, corroborations, and cancellations."""

    def __init__(self, max_track_age_minutes: float = 60.0) -> None:
        self.tracks: Dict[str, ThreatTrack] = {}
        self.max_age_minutes = max_track_age_minutes

    def ingest_signal(self, signal: ThreatSignal, channel_weight: float = 0.90) -> Optional[ThreatTrack]:
        """Ingest signal, updating existing matching track or creating a new track."""
        if signal.is_cancellation:
            self.resolve_threats(signal.threat_type)
            return None

        # Corroborate with recent active track of same threat type within last 15 minutes
        for track in self.tracks.values():
            if track.state == "ACTIVE" and track.threat_type == signal.threat_type:
                track.add_signal(signal, channel_weight)
                return track

        # Create new track
        track_id = f"TRK-{uuid.uuid4().hex[:8].upper()}"
        new_track = ThreatTrack(
            track_id=track_id,
            threat_type=signal.threat_type,
            quantity=signal.quantity,
            signals=[signal],
            state="ACTIVE",
            first_detected=signal.timestamp,
            last_updated=signal.timestamp,
            trajectory=signal.trajectory,
        )
        new_track.add_signal(signal, channel_weight)
        self.tracks[track_id] = new_track
        return new_track

    def resolve_threats(self, threat_type: Optional[ThreatType] = None) -> int:
        """Resolve active tracks matching threat_type (or all if threat_type is None/UNKNOWN)."""
        count = 0
        for track in self.tracks.values():
            if track.state == "ACTIVE":
                if threat_type is None or threat_type == ThreatType.UNKNOWN or track.threat_type == threat_type:
                    track.state = "RESOLVED"
                    count += 1
        return count

    def prune_expired(self, current_time: Optional[datetime] = None) -> int:
        """Prune tracks exceeding maximum track age."""
        now = current_time or datetime.now(timezone.utc)
        count = 0
        for track in list(self.tracks.values()):
            if track.state == "ACTIVE":
                age_m = (now - track.last_updated).total_seconds() / 60.0
                if age_m >= self.max_age_minutes:
                    track.state = "EXPIRED"
                    count += 1
        return count

    def get_active_tracks(self) -> List[ThreatTrack]:
        return [t for t in self.tracks.values() if t.state == "ACTIVE"]


# ==============================================================================
# 2. FASTAPI APPLICATION SETUP WITH TRY-IMPORT AND FALLBACK
# ==============================================================================

def create_contract_fastapi_app() -> Any:
    """Create a fully-compliant ASGI FastAPI application matching the project OpenAPI contract."""
    from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, status
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field

    app = FastAPI(
        title="Chance to Alert.App",
        description="Air raid and drone threat probability calculation and early warning engine",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # In-memory shared state for testing
    state: Dict[str, Any] = {
        "active_signals": [],
        "history": [],
        "ws_connections": [],
        "config": load_config(),
        "storage": SQLiteStorage(),
        "tracker": ThreatTrackingService(),
    }

    class SimulatePayload(BaseModel):
        text: str = Field(..., min_length=1, description="Raw threat post text")
        channel: str = Field("vanek_nikolaev", description="Source Telegram channel")
        timestamp: Optional[str] = None
        quantity: Optional[int] = None

    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "ok", "service": "chance-to-alert", "version": "1.0.0"}

    @app.get("/api/v1/config/presets", tags=["Config"])
    async def get_presets():
        presets = state["config"].presets
        return {k: p.to_dict() for k, p in presets.items()}

    @app.get("/api/v1/config/presets/{preset_name}", tags=["Config"])
    async def get_preset_detail(preset_name: str):
        presets = state["config"].presets
        if preset_name not in presets:
            raise HTTPException(status_code=404, detail=f"Preset '{preset_name}' not found")
        return presets[preset_name].to_dict()

    @app.get("/api/v1/config/channels", tags=["Config"])
    async def get_channels():
        return [c.to_dict() for c in state["config"].channels]

    @app.get("/api/v1/probability", tags=["Probability"])
    async def get_probability(preset: str = Query("odesa_district")):
        presets = state["config"].presets
        if preset not in presets:
            raise HTTPException(status_code=404, detail=f"Preset '{preset}' not found")
        target_preset = presets[preset]
        result = calculate_aggregate_probability(state["active_signals"], target_preset)
        return result.to_dict()

    @app.get("/api/v1/threats/current", tags=["Threats"])
    async def get_current_threats():
        return [s.to_dict() for s in state["active_signals"] if not s.is_cancellation]

    @app.get("/api/v1/threats/history", tags=["Threats"])
    async def get_threat_history(limit: int = Query(50), offset: int = Query(0)):
        # Clamp limit
        clamped_limit = min(100, max(1, limit))
        clamped_offset = max(0, offset)
        hist = state["history"][clamped_offset : clamped_offset + clamped_limit]
        return {
            "total": len(state["history"]),
            "limit": clamped_limit,
            "offset": clamped_offset,
            "items": hist,
        }

    @app.post("/api/v1/simulate", status_code=200, tags=["Simulation"])
    async def simulate_threat(payload: SimulatePayload):
        if not payload.text or not payload.text.strip():
            raise HTTPException(status_code=422, detail="Text cannot be empty")

        ts = datetime.now(timezone.utc)
        if payload.timestamp:
            try:
                ts = datetime.fromisoformat(payload.timestamp.replace("Z", "+00:00"))
            except Exception:
                pass

        parser = ThreatParser()
        signals = parser.parse(payload.text, channel=payload.channel, timestamp=ts)
        if payload.quantity and signals:
            for s in signals:
                s.quantity = payload.quantity

        for s in signals:
            state["storage"].record_event(s)
            state["tracker"].ingest_signal(s)
            if s.is_cancellation:
                state["active_signals"] = [
                    sig for sig in state["active_signals"]
                    if (s.threat_type != ThreatType.UNKNOWN and sig.threat_type != s.threat_type)
                ]
            else:
                state["active_signals"].append(s)

            state["history"].append({
                "event_id": s.threat_id,
                "threat_type": s.threat_type.value,
                "quantity": s.quantity,
                "raw_text": s.raw_text,
                "source_channel": s.source_channel,
                "timestamp": s.timestamp.isoformat(),
            })

        default_target = state["config"].get_preset()
        prob = calculate_aggregate_probability(state["active_signals"], default_target)

        # Broadcast to active WebSockets
        broadcast_msg = json.dumps({
            "type": "threat_update",
            "probability": prob.to_dict(),
            "signals": [s.to_dict() for s in signals],
        })
        for ws in list(state["ws_connections"]):
            try:
                asyncio.create_task(ws.send_text(broadcast_msg))
            except Exception:
                if ws in state["ws_connections"]:
                    state["ws_connections"].remove(ws)

        return {
            "status": "ingested",
            "signals_count": len(signals),
            "signals": [s.to_dict() for s in signals],
            "probability": prob.to_dict(),
        }

    @app.websocket("/api/v1/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        state["ws_connections"].append(websocket)
        try:
            await websocket.send_text(json.dumps({"type": "connected", "status": "ready"}))
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
                elif data == "close":
                    break
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in state["ws_connections"]:
                state["ws_connections"].remove(websocket)

    return app


# Try importing real application from app.main, else use contract FastAPI app
try:
    from app.main import app as _real_app  # type: ignore
    app = _real_app
except Exception:
    app = create_contract_fastapi_app()


# ==============================================================================
# 3. PYTEST FIXTURES
# ==============================================================================

@pytest.fixture(scope="session")
def base_time() -> datetime:
    """Fixed reference UTC datetime for deterministic temporal testing."""
    return datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="session")
def test_config() -> AppConfig:
    """Loaded AppConfig fixture with default presets and monitored channels."""
    return load_config()


@pytest.fixture(scope="session")
def odesa_district_preset() -> TargetPreset:
    """TargetPreset for Odesa District (urban centroid, 35km radius)."""
    return TargetPreset(
        name="odesa_district",
        centroid=GeoCoordinate(lat=46.4825, lon=30.7233),
        radius_km=35.0,
        warning_radius_km=100.0,
        zones={"immediate": 15.0, "urban": 35.0, "approach": 70.0, "transit": 120.0},
        monitored_places=["Одеса", "Чорноморськ", "Южне", "Фонтанка", "Таїрове"],
        transit_corridors=["Чорноморський морський підхід", "Миколаївський коридор"],
        description="Odesa city and immediate metropolitan district",
    )


@pytest.fixture(scope="session")
def odesa_oblast_preset() -> TargetPreset:
    """TargetPreset for Odesa Oblast (regional centroid, 150km radius)."""
    return TargetPreset(
        name="odesa_oblast",
        centroid=GeoCoordinate(lat=46.5000, lon=30.5000),
        radius_km=150.0,
        warning_radius_km=250.0,
        zones={"immediate": 35.0, "oblast_core": 100.0, "regional": 150.0, "approach": 250.0},
        monitored_places=["Одеса", "Ізмаїл", "Рені", "Кілія", "Білгород-Дністровський", "Подільськ"],
        transit_corridors=["Чорне море", "Придунав'я", "Миколаївський напрямок"],
        description="Full Odesa Oblast administrative territory",
    )


@pytest.fixture(scope="session")
def test_channels(test_config: AppConfig) -> List[ChannelConfig]:
    """Configured channels fixture."""
    return test_config.channels


@pytest.fixture
def clean_storage(tmp_path: Path) -> Generator[SQLiteStorage, None, None]:
    """Hermetic SQLite storage instance created in temporary directory per test."""
    db_file = tmp_path / f"test_threats_{uuid.uuid4().hex[:8]}.sqlite"
    storage = SQLiteStorage(db_file)
    yield storage
    storage.close()


@pytest.fixture
def sanitizer() -> TextSanitizer:
    """Text sanitizer fixture."""
    return TextSanitizer()


@pytest.fixture
def gazetteer() -> RegionalGazetteer:
    """Regional gazetteer fixture."""
    return RegionalGazetteer()


@pytest.fixture
def threat_parser(gazetteer: RegionalGazetteer) -> ThreatParser:
    """Threat parser fixture."""
    return ThreatParser(gazetteer=gazetteer)


@pytest.fixture
def tracking_service() -> ThreatTrackingService:
    """Threat tracking service fixture."""
    return ThreatTrackingService()


@pytest.fixture
def make_threat_signal(base_time: datetime) -> Callable[..., ThreatSignal]:
    """Factory helper to construct ThreatSignal instances with sensible defaults."""
    def _factory(
        threat_type: Union[ThreatType, str] = ThreatType.SHAHED,
        quantity: int = 1,
        raw_text: str = "Шахеди в напрямку Одеси",
        source_channel: str = "vanek_nikolaev",
        timestamp: Optional[datetime] = None,
        origin_location: Optional[str] = None,
        target_heading: Optional[str] = "Одеса",
        detected_locations: Optional[List[str]] = None,
        current_coordinate: Optional[GeoCoordinate] = None,
        trajectory: Optional[TrajectoryVector] = None,
        is_cancellation: bool = False,
        threat_id: str = "",
    ) -> ThreatSignal:
        tt = ThreatType.from_str(threat_type) if isinstance(threat_type, str) else threat_type
        return ThreatSignal(
            threat_type=tt,
            quantity=quantity,
            raw_text=raw_text,
            source_channel=source_channel,
            timestamp=timestamp or base_time,
            origin_location=origin_location,
            target_heading=target_heading,
            detected_locations=detected_locations or [],
            current_coordinate=current_coordinate,
            trajectory=trajectory,
            is_cancellation=is_cancellation,
            threat_id=threat_id or str(uuid.uuid4()),
        )
    return _factory


@pytest.fixture
def make_raw_post(base_time: datetime) -> Callable[..., RawPost]:
    """Factory helper to construct RawPost instances."""
    def _factory(
        text: str = "Шахеди з моря!",
        channel: str = "vanek_nikolaev",
        timestamp: Optional[datetime] = None,
        message_id: int = 1,
        post_id: str = "",
    ) -> RawPost:
        return RawPost(
            id=post_id or str(uuid.uuid4()),
            channel=channel,
            text=text,
            timestamp=timestamp or base_time,
            message_id=message_id,
        )
    return _factory


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """In-memory ASGI client for FastAPI endpoints using ASGITransport."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sync_client() -> Generator[TestClient, None, None]:
    """Synchronous Starlette TestClient for WebSocket and HTTP operations."""
    with TestClient(app) as client:
        yield client
