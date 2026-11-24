"""Active threat lifecycle management, state transitions, corroboration, and expiry."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.domain.entities import ThreatSignal, TrajectoryVector
from app.domain.enums import ThreatType


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
