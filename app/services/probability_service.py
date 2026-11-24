"""Real-time calculation service computing threat likelihood for configured presets."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from app.config import AppConfig, TargetPreset, get_config
from app.domain.entities import ProbabilityResult, ThreatSignal
from app.domain.scoring import ScoringConfig, calculate_aggregate_probability
from app.services.tracking_service import ThreatTrackingService


class ProbabilityCalculationService:
    """Computes current alert likelihood scores based on active signals and targets."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        scoring_config: Optional[ScoringConfig] = None,
    ) -> None:
        self.config = config or get_config()
        self.scoring_config = scoring_config

    def calculate(
        self,
        signals: List[ThreatSignal],
        preset_name: Optional[str] = None,
        reference_time: Optional[datetime] = None,
    ) -> ProbabilityResult:
        """Calculate threat probability for specified preset using active signals."""
        target = self.config.get_preset(preset_name)
        ref_time = reference_time or datetime.now(timezone.utc)
        return calculate_aggregate_probability(
            signals=signals,
            target=target,
            current_time=ref_time,
            config=self.scoring_config,
        )

    def calculate_from_tracker(
        self,
        tracker: ThreatTrackingService,
        preset_name: Optional[str] = None,
        reference_time: Optional[datetime] = None,
    ) -> ProbabilityResult:
        """Extract active signals from tracking service and calculate probability."""
        active_signals: List[ThreatSignal] = []
        for track in tracker.get_active_tracks():
            if track.signals:
                latest_sig = track.signals[-1]
                latest_sig.quantity = track.quantity
                active_signals.append(latest_sig)

        return self.calculate(
            signals=active_signals,
            preset_name=preset_name,
            reference_time=reference_time,
        )
