"""Integration tests for threat tracking lifecycle and corroboration."""

from datetime import datetime, timedelta, timezone
import pytest
from app.domain.entities import ThreatSignal
from app.domain.enums import ThreatType
from app.services.tracking_service import ThreatTrackingService


@pytest.fixture
def tracker():
    return ThreatTrackingService(max_track_age_minutes=30.0)


class TestThreatTrackingService:
    def test_ingest_signal_creates_track(self, tracker):
        sig = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            quantity=2,
            raw_text="2 БПЛА",
            source_channel="chan1",
        )
        track = tracker.ingest_signal(sig)
        assert track is not None
        assert track.state == "ACTIVE"
        assert track.threat_type == ThreatType.SHAHED
        assert track.quantity == 2
        assert len(tracker.get_active_tracks()) == 1

    def test_corroboration_from_multiple_channels(self, tracker):
        sig1 = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            quantity=2,
            raw_text="2 БПЛА",
            source_channel="chan1",
        )
        sig2 = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            quantity=4,
            raw_text="Уточнення: 4 БПЛА",
            source_channel="chan2",
        )
        track1 = tracker.ingest_signal(sig1)
        initial_confidence = track1.confidence_score

        track2 = tracker.ingest_signal(sig2)
        assert track1.track_id == track2.track_id
        assert track2.quantity == 4
        # Multi-channel corroboration elevates confidence
        assert track2.confidence_score > initial_confidence
        assert len(tracker.get_active_tracks()) == 1

    def test_cancellation_resolves_tracks(self, tracker):
        sig = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            quantity=1,
            raw_text="БПЛА над морем",
            source_channel="chan1",
        )
        tracker.ingest_signal(sig)
        assert len(tracker.get_active_tracks()) == 1

        cancel_sig = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            quantity=1,
            raw_text="Відбій по БПЛА",
            source_channel="chan1",
            is_cancellation=True,
        )
        tracker.ingest_signal(cancel_sig)
        assert len(tracker.get_active_tracks()) == 0

    def test_prune_expired_tracks(self, tracker):
        t0 = datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)
        sig = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            quantity=1,
            raw_text="Старий дрон",
            timestamp=t0,
        )
        tracker.ingest_signal(sig)
        assert len(tracker.get_active_tracks()) == 1

        # Check after 40 minutes (max age is 30m)
        t_after = t0 + timedelta(minutes=40)
        pruned = tracker.prune_expired(current_time=t_after)
        assert pruned == 1
        assert len(tracker.get_active_tracks()) == 0
