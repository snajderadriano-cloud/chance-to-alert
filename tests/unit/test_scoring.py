"""Unit test suite for app.domain.scoring and domain entities/taxonomy."""

import math
from datetime import datetime, timedelta, timezone
import pytest

from app.config import AppConfig, get_preset, list_channels, list_presets, load_config
from app.domain.entities import (
    GeoCoordinate,
    ProbabilityResult,
    TargetPreset,
    ThreatContribution,
    ThreatSignal,
    TrajectoryVector,
)
from app.domain.enums import AlertLevel, MovementSpeedClass, ThreatType
from app.domain.scoring import (
    DEFAULT_SCORING_CONFIG,
    ScoringConfig,
    calculate_aggregate_probability,
    calculate_distance_decay,
    calculate_swarm_multiplier,
    calculate_temporal_decay,
    calculate_threat_probability,
)


@pytest.fixture
def odesa_district_preset() -> TargetPreset:
    """Fixture providing standard Odesa District preset."""
    return TargetPreset(
        name="Odesa District",
        centroid=GeoCoordinate(lat=46.4825, lon=30.7233),
        radius_km=35.0,
        warning_radius_km=100.0,
        zones={"immediate": 15.0, "urban": 35.0, "approach": 70.0, "transit": 120.0},
        monitored_places=["Одеса", "Чорноморськ", "Южне", "Фонтанка", "Таїрове"],
        transit_corridors=["Чорноморський морський підхід", "Миколаївський коридор"],
    )


class TestAlertLevelTaxonomy:
    """Tests for AlertLevel enum and probability threshold mapping."""

    def test_alert_level_thresholds(self) -> None:
        # GREEN: 0% to 24%
        assert AlertLevel.from_probability(0) == AlertLevel.GREEN
        assert AlertLevel.from_probability(15.5) == AlertLevel.GREEN
        assert AlertLevel.from_probability(24.9) == AlertLevel.GREEN

        # YELLOW: 25% to 49%
        assert AlertLevel.from_probability(25.0) == AlertLevel.YELLOW
        assert AlertLevel.from_probability(35.0) == AlertLevel.YELLOW
        assert AlertLevel.from_probability(49.9) == AlertLevel.YELLOW

        # ORANGE: 50% to 74%
        assert AlertLevel.from_probability(50.0) == AlertLevel.ORANGE
        assert AlertLevel.from_probability(65.0) == AlertLevel.ORANGE
        assert AlertLevel.from_probability(74.9) == AlertLevel.ORANGE

        # RED: 75% to 100%
        assert AlertLevel.from_probability(75.0) == AlertLevel.RED
        assert AlertLevel.from_probability(90.0) == AlertLevel.RED
        assert AlertLevel.from_probability(100.0) == AlertLevel.RED

    def test_out_of_bounds_clamping(self) -> None:
        assert AlertLevel.from_probability(-15.0) == AlertLevel.GREEN
        assert AlertLevel.from_probability(150.0) == AlertLevel.RED


class TestThreatTypeTaxonomy:
    """Tests for ThreatType parsing and string conversions."""

    def test_from_str_case_insensitivity(self) -> None:
        assert ThreatType.from_str("shahed") == ThreatType.SHAHED
        assert ThreatType.from_str("BALLISTIC") == ThreatType.BALLISTIC
        assert ThreatType.from_str("cruise_missile") == ThreatType.CRUISE_MISSILE
        assert ThreatType.from_str("tactical-aviation") == ThreatType.TACTICAL_AVIATION
        assert ThreatType.from_str("recon drone") == ThreatType.RECON_DRONE

    def test_from_str_unknown_fallback(self) -> None:
        assert ThreatType.from_str("unidentified_ufo") == ThreatType.UNKNOWN


class TestMovementSpeedClass:
    """Tests for kinematic speeds per threat class."""

    def test_nominal_speeds(self) -> None:
        assert MovementSpeedClass.get_speed_for_threat(ThreatType.SHAHED) == 185.0
        assert MovementSpeedClass.get_speed_for_threat(ThreatType.BALLISTIC) == 4000.0
        assert MovementSpeedClass.get_speed_for_threat(ThreatType.CRUISE_MISSILE) == 850.0
        assert MovementSpeedClass.get_speed_for_threat(ThreatType.TACTICAL_AVIATION) == 900.0
        assert MovementSpeedClass.get_speed_for_threat(ThreatType.RECON_DRONE) == 120.0
        assert MovementSpeedClass.get_speed_for_threat(ThreatType.UNKNOWN) == 250.0


class TestTemporalDecayMath:
    """Tests for exponential half-life decay function."""

    def test_zero_elapsed_returns_one(self) -> None:
        assert calculate_temporal_decay(elapsed_minutes=0.0, half_life_minutes=25.0) == 1.0

    def test_future_timestamp_returns_one(self) -> None:
        assert calculate_temporal_decay(elapsed_minutes=-5.0, half_life_minutes=25.0) == 1.0

    def test_half_life_exact_decay(self) -> None:
        decay = calculate_temporal_decay(elapsed_minutes=25.0, half_life_minutes=25.0)
        assert math.isclose(decay, 0.50, rel_tol=1e-5)

    def test_two_half_lives_decay(self) -> None:
        decay = calculate_temporal_decay(elapsed_minutes=50.0, half_life_minutes=25.0)
        assert math.isclose(decay, 0.25, rel_tol=1e-5)

    def test_max_age_expired_returns_zero(self) -> None:
        assert calculate_temporal_decay(elapsed_minutes=125.0, half_life_minutes=25.0, max_age_minutes=120.0) == 0.0


class TestDistanceDecayMath:
    """Tests for spatial distance decay curve."""

    def test_inside_target_radius_factor_is_one(self) -> None:
        # Target radius 35 km
        assert calculate_distance_decay(distance_km=10.0, target_radius_km=35.0, warning_radius_km=100.0) == 1.0
        assert calculate_distance_decay(distance_km=35.0, target_radius_km=35.0, warning_radius_km=100.0) == 1.0

    def test_at_warning_radius_factor_is_half(self) -> None:
        factor = calculate_distance_decay(distance_km=100.0, target_radius_km=35.0, warning_radius_km=100.0)
        assert math.isclose(factor, 0.50, rel_tol=1e-4)

    def test_distance_decay_monotonicity(self) -> None:
        distances = [35.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0]
        factors = [calculate_distance_decay(d, 35.0, 100.0) for d in distances]
        for i in range(len(factors) - 1):
            assert factors[i] >= factors[i + 1]


class TestSwarmMultiplier:
    """Tests for diminishing returns quantity multiplier."""

    def test_single_unit(self) -> None:
        assert calculate_swarm_multiplier(1) == 1.0

    def test_zero_or_negative(self) -> None:
        assert calculate_swarm_multiplier(0) == 1.0
        assert calculate_swarm_multiplier(-3) == 1.0

    def test_multiple_units(self) -> None:
        # factor = 0.30 -> n=2: 1 + 0.30*1 = 1.30
        assert math.isclose(calculate_swarm_multiplier(2, factor=0.30), 1.30, rel_tol=1e-4)
        # n=4: 1 + 0.30*2 = 1.60
        assert math.isclose(calculate_swarm_multiplier(4, factor=0.30), 1.60, rel_tol=1e-4)
        # n=8: 1 + 0.30*3 = 1.90
        assert math.isclose(calculate_swarm_multiplier(8, factor=0.30), 1.90, rel_tol=1e-4)

    def test_max_multiplier_cap(self) -> None:
        # Huge quantity caps at max_multiplier (e.g. 2.50)
        assert calculate_swarm_multiplier(1000, max_multiplier=2.50) == 2.50


class TestThreatProbabilityCalculation:
    """Tests for individual ThreatContribution scoring."""

    def test_cancellation_signal_yields_zero(self, odesa_district_preset: TargetPreset) -> None:
        now = datetime.now(timezone.utc)
        sig = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            quantity=1,
            is_cancellation=True,
            timestamp=now,
        )
        contrib = calculate_threat_probability(sig, odesa_district_preset, current_time=now)
        assert contrib.decayed_probability == 0.0
        assert contrib.raw_probability == 0.0

    def test_inbound_vs_outbound_shahed(self, odesa_district_preset: TargetPreset) -> None:
        now = datetime.now(timezone.utc)
        # Position 50 km south of Odesa (46.03, 30.7233)
        threat_pos = GeoCoordinate(lat=46.03, lon=30.7233)

        # Inbound heading: 0° (North directly towards Odesa)
        sig_inbound = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            current_coordinate=threat_pos,
            trajectory=TrajectoryVector(current=threat_pos, heading_degrees=0.0, speed_kmh=185.0),
            timestamp=now,
        )

        # Outbound heading: 180° (South away into sea)
        sig_outbound = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            current_coordinate=threat_pos,
            trajectory=TrajectoryVector(current=threat_pos, heading_degrees=180.0, speed_kmh=185.0),
            timestamp=now,
        )

        contrib_inbound = calculate_threat_probability(sig_inbound, odesa_district_preset, current_time=now)
        contrib_outbound = calculate_threat_probability(sig_outbound, odesa_district_preset, current_time=now)

        assert contrib_inbound.decayed_probability > 0.45
        assert contrib_outbound.decayed_probability == 0.0  # cos=0 when 180° away

    def test_ballistic_threat_urgency(self, odesa_district_preset: TargetPreset) -> None:
        now = datetime.now(timezone.utc)
        # Ballistic missile reported in Black Sea transit corridor
        launch_pos = GeoCoordinate(lat=45.0, lon=31.5)
        sig = ThreatSignal(
            threat_type=ThreatType.BALLISTIC,
            current_coordinate=launch_pos,
            timestamp=now,
        )
        contrib = calculate_threat_probability(sig, odesa_district_preset, current_time=now)
        # Base weight is 0.90, ballistic is heading-invariant
        assert contrib.decayed_probability > 0.20


class TestMultiThreatAggregateScoring:
    """Tests for multi-threat union, cancellation, and alert level classification."""

    def test_empty_signals_calm_state(self, odesa_district_preset: TargetPreset) -> None:
        result = calculate_aggregate_probability([], odesa_district_preset)
        assert result.probability_percent == 0
        assert result.alert_level == AlertLevel.GREEN
        assert result.active_threat_count == 0
        assert result.primary_threat_type is None
        assert "calm" in result.summary.lower()

    def test_cancellation_neutralization(self, odesa_district_preset: TargetPreset) -> None:
        now = datetime.now(timezone.utc)
        t_minus_5 = now - timedelta(minutes=5)
        t_minus_1 = now - timedelta(minutes=1)

        pos = GeoCoordinate(lat=46.30, lon=30.72)
        # Threat detected 5 min ago
        threat_sig = ThreatSignal(
            threat_id="threat-1",
            threat_type=ThreatType.SHAHED,
            current_coordinate=pos,
            timestamp=t_minus_5,
            trajectory=TrajectoryVector(current=pos, heading_degrees=0.0),
        )

        # All-clear signal emitted 1 min ago
        clear_sig = ThreatSignal(
            threat_id="clear-1",
            threat_type=ThreatType.SHAHED,
            is_cancellation=True,
            timestamp=t_minus_1,
        )

        # Before cancellation: threat gives elevated probability
        res_active = calculate_aggregate_probability([threat_sig], odesa_district_preset, current_time=now)
        assert res_active.probability_percent > 30

        # With cancellation: threat neutralized to 0% GREEN
        res_cleared = calculate_aggregate_probability([threat_sig, clear_sig], odesa_district_preset, current_time=now)
        assert res_cleared.probability_percent == 0
        assert res_cleared.alert_level == AlertLevel.GREEN
        assert res_cleared.active_threat_count == 0

    def test_probabilistic_union_two_independent_threats(self, odesa_district_preset: TargetPreset) -> None:
        now = datetime.now(timezone.utc)
        pos = GeoCoordinate(lat=46.40, lon=30.72)

        # Create two individual threats
        t1 = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            current_coordinate=pos,
            timestamp=now,
            trajectory=TrajectoryVector(current=pos, heading_degrees=0.0),
        )
        t2 = ThreatSignal(
            threat_type=ThreatType.CRUISE_MISSILE,
            current_coordinate=pos,
            timestamp=now,
            trajectory=TrajectoryVector(current=pos, heading_degrees=0.0),
        )

        r1 = calculate_aggregate_probability([t1], odesa_district_preset, current_time=now)
        r2 = calculate_aggregate_probability([t2], odesa_district_preset, current_time=now)
        r_both = calculate_aggregate_probability([t1, t2], odesa_district_preset, current_time=now)

        # P_union = 1 - (1 - P1)*(1 - P2) > max(P1, P2)
        assert r_both.probability_percent >= max(r1.probability_percent, r2.probability_percent)
        assert r_both.active_threat_count == 2
        assert r_both.alert_level in (AlertLevel.ORANGE, AlertLevel.RED)

    def test_swarm_alert_level_reaches_red(self, odesa_district_preset: TargetPreset) -> None:
        now = datetime.now(timezone.utc)
        # Swarm of 6 Shaheds detected 25 km away moving North directly to Odesa
        pos = GeoCoordinate(lat=46.25, lon=30.7233)
        swarm_sig = ThreatSignal(
            threat_type=ThreatType.SHAHED,
            quantity=6,
            current_coordinate=pos,
            timestamp=now,
            trajectory=TrajectoryVector(current=pos, heading_degrees=0.0, speed_kmh=185.0),
        )

        result = calculate_aggregate_probability([swarm_sig], odesa_district_preset, current_time=now)
        assert result.alert_level == AlertLevel.RED
        assert result.probability_percent >= 75
        assert result.primary_threat_type == ThreatType.SHAHED
        assert result.estimated_time_to_impact_minutes is not None
        assert result.estimated_time_to_impact_minutes <= 15


class TestAppConfigAndPresets:
    """Tests for YAML preset loading and configuration loader."""

    def test_load_presets_odesa(self) -> None:
        cfg = load_config()
        assert "odesa_district" in cfg.presets
        assert "odesa_oblast" in cfg.presets

        district = cfg.get_preset("odesa_district")
        assert district.name == "Odesa District"
        assert math.isclose(district.centroid.lat, 46.4825, abs_tol=0.01)
        assert math.isclose(district.centroid.lon, 30.7233, abs_tol=0.01)
        assert district.radius_km == 35.0
        assert district.warning_radius_km == 100.0
        assert len(district.monitored_places) >= 10

        oblast = cfg.get_preset("odesa_oblast")
        assert oblast.name == "Odesa Oblast"
        assert oblast.radius_km == 150.0

    def test_load_channels(self) -> None:
        cfg = load_config()
        assert len(cfg.channels) >= 4
        vanek = next((c for c in cfg.channels if c.id == "vanek_nikolaev"), None)
        assert vanek is not None
        assert vanek.reliability_weight >= 0.90
        assert ThreatType.SHAHED in vanek.threat_focus

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TARGET_DISTRICT", "odesa_oblast")
        cfg = load_config()
        assert cfg.default_preset == "odesa_oblast"
        preset = cfg.get_preset()
        assert preset.name == "Odesa Oblast"
