"""Probability scoring engine with exponential decay, spatial curves, and multi-threat union.

Implements tactical air defense risk scoring:
1. Base threat urgency weights per ThreatType
2. Exponential temporal decay: P(t) = P_0 * 2^(-delta_t / half_life)
3. Distance decay function relative to target centroid & radius
4. Heading alignment directional multiplier
5. Diminishing returns swarm/quantity multiplier
6. All-clear cancellation neutralization
7. Multi-threat probabilistic union: P_total = 1 - prod(1 - P_i)
8. Four-tier AlertLevel classification (GREEN, YELLOW, ORANGE, RED)

Zero external framework dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

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
    calculate_heading_alignment_factor,
    estimate_time_to_target,
    haversine_distance,
)


@dataclass
class ScoringConfig:
    """Configurable weights, half-life parameters, and multipliers for probability scoring."""

    # Base threat urgency weights P_base in [0.0, 1.0]
    base_weights: Dict[ThreatType, float] = field(
        default_factory=lambda: {
            ThreatType.BALLISTIC: 0.90,
            ThreatType.CRUISE_MISSILE: 0.80,
            ThreatType.SHAHED: 0.70,
            ThreatType.TACTICAL_AVIATION: 0.50,
            ThreatType.RECON_DRONE: 0.30,
            ThreatType.UNKNOWN: 0.40,
        }
    )

    # Half-life T_1/2 in minutes for exponential temporal decay
    half_lives_minutes: Dict[ThreatType, float] = field(
        default_factory=lambda: {
            ThreatType.BALLISTIC: 10.0,
            ThreatType.CRUISE_MISSILE: 15.0,
            ThreatType.SHAHED: 25.0,
            ThreatType.TACTICAL_AVIATION: 20.0,
            ThreatType.RECON_DRONE: 30.0,
            ThreatType.UNKNOWN: 20.0,
        }
    )

    # Maximum age in minutes after which a signal is deemed expired (probability = 0)
    max_signal_age_minutes: float = 120.0

    # Swarm logarithmic multiplier factor: M(n) = 1 + swarm_factor * log2(n)
    swarm_factor: float = 0.30
    max_swarm_multiplier: float = 2.50

    # Default regional distance factor when threat coordinate is unknown but within region
    unknown_coord_distance_factor: float = 0.60

    # Fallback speeds in km/h if not provided in trajectory
    speeds_kmh: Dict[ThreatType, float] = field(
        default_factory=lambda: {
            ThreatType.BALLISTIC: MovementSpeedClass.BALLISTIC.value,
            ThreatType.CRUISE_MISSILE: MovementSpeedClass.CRUISE_MISSILE.value,
            ThreatType.SHAHED: MovementSpeedClass.SHAHED.value,
            ThreatType.TACTICAL_AVIATION: MovementSpeedClass.TACTICAL_AVIATION.value,
            ThreatType.RECON_DRONE: MovementSpeedClass.RECON_DRONE.value,
            ThreatType.UNKNOWN: MovementSpeedClass.UNKNOWN.value,
        }
    )


# Default scoring configuration instance
DEFAULT_SCORING_CONFIG = ScoringConfig()


def calculate_temporal_decay(
    elapsed_minutes: float,
    half_life_minutes: float,
    max_age_minutes: float = 120.0,
) -> float:
    """Calculate exponential temporal decay factor in range [0.0, 1.0].

    Formula: decay = 2^(-elapsed / half_life)
    If elapsed < 0 (future timestamp due to clock drift): returns 1.0.
    If elapsed >= max_age: returns 0.0.
    """
    if elapsed_minutes <= 0.0:
        return 1.0
    if elapsed_minutes >= max_age_minutes:
        return 0.0
    if half_life_minutes <= 0.0:
        return 0.0

    exponent = -elapsed_minutes / half_life_minutes
    decay = math.pow(2.0, exponent)
    return max(0.0, min(1.0, decay))


def calculate_distance_decay(
    distance_km: float,
    target_radius_km: float,
    warning_radius_km: float,
) -> float:
    """Calculate distance decay factor relative to target perimeter and warning radius.

    Behavior:
    - distance <= target_radius: threat is inside the target zone -> factor = 1.0
    - distance == warning_radius: factor = 0.50
    - distance > warning_radius: decays smoothly towards 0.0
    """
    if distance_km <= target_radius_km:
        return 1.0

    # Scale factor such that at distance == warning_radius_km, factor is exactly 0.5
    excess_distance = distance_km - target_radius_km
    delta_warning = max(1.0, warning_radius_km - target_radius_km)
    scale = delta_warning / math.log(2.0)

    factor = math.exp(-excess_distance / scale)
    return max(0.0, min(1.0, factor))


def calculate_swarm_multiplier(quantity: int, factor: float = 0.30, max_multiplier: float = 2.50) -> float:
    """Calculate diminishing returns multiplier for swarm / multiple threat counts.

    Formula: M(n) = 1.0 + factor * log2(n) for n >= 1, capped at max_multiplier.
    """
    if quantity <= 1:
        return 1.0
    multiplier = 1.0 + factor * math.log2(float(quantity))
    return min(max_multiplier, multiplier)


def calculate_threat_probability(
    signal: ThreatSignal,
    target: TargetPreset,
    current_time: Optional[datetime] = None,
    config: Optional[ScoringConfig] = None,
    reference_time: Optional[datetime] = None,
) -> ThreatContribution:
    """Calculate the individual threat probability contribution for a given threat signal.

    Takes into account:
    - ThreatType base weight
    - Temporal decay since signal emission
    - Spatial distance from threat to target centroid
    - Trajectory heading alignment factor
    - Swarm quantity multiplier
    - Cancellation status
    """
    cfg = config or DEFAULT_SCORING_CONFIG

    # Cancellation signals contribute 0.0
    if signal.is_cancellation:
        return ThreatContribution(
            threat_id=signal.threat_id,
            threat_type=signal.threat_type,
            raw_probability=0.0,
            decayed_probability=0.0,
            distance_km=None,
            heading_factor=None,
            time_to_impact_minutes=None,
            description=f"Cancelled threat ({signal.threat_type.value})",
        )

    # 1. Base threat weight
    base_weight = cfg.base_weights.get(signal.threat_type, cfg.base_weights[ThreatType.UNKNOWN])

    # 2. Temporal decay
    now = current_time or reference_time or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    sig_time = signal.timestamp
    if sig_time.tzinfo is None:
        sig_time = sig_time.replace(tzinfo=timezone.utc)

    elapsed_minutes = (now - sig_time).total_seconds() / 60.0
    half_life = cfg.half_lives_minutes.get(signal.threat_type, 20.0)
    temporal_factor = calculate_temporal_decay(
        elapsed_minutes,
        half_life,
        cfg.max_signal_age_minutes,
    )

    if temporal_factor <= 0.0:
        return ThreatContribution(
            threat_id=signal.threat_id,
            threat_type=signal.threat_type,
            raw_probability=base_weight,
            decayed_probability=0.0,
            distance_km=None,
            heading_factor=None,
            time_to_impact_minutes=None,
            description=f"Expired signal ({elapsed_minutes:.1f} min old)",
        )

    # 3. Spatial & Heading factors
    threat_coord = signal.current_coordinate
    if threat_coord is None and signal.trajectory and signal.trajectory.current:
        threat_coord = signal.trajectory.current

    distance_km: Optional[float] = None
    dist_factor: float = 1.0
    heading_factor: Optional[float] = None
    time_to_impact: Optional[float] = None

    if threat_coord is not None:
        distance_km = haversine_distance(threat_coord, target.centroid)
        warning_rad = (
            max(target.warning_radius_km, 450.0)
            if signal.threat_type == ThreatType.BALLISTIC
            else target.warning_radius_km
        )
        dist_factor = calculate_distance_decay(
            distance_km=distance_km,
            target_radius_km=target.radius_km,
            warning_radius_km=warning_rad,
        )

        # Heading alignment
        heading_deg: Optional[float] = None
        if signal.trajectory and signal.trajectory.heading_degrees is not None:
            heading_deg = signal.trajectory.heading_degrees

        # Ballistic threats are less heading-dependent due to high speed/range
        if signal.threat_type == ThreatType.BALLISTIC:
            heading_factor = 1.0
            if signal.target_heading and any(w in signal.target_heading.lower() for w in ("одес", target.name.lower())):
                dist_factor = max(dist_factor, 0.98)
        else:
            heading_factor = calculate_heading_alignment_factor(
                threat_coord=threat_coord,
                heading_degrees=heading_deg,
                target_coord=target.centroid,
            )

        # Speed and time to target
        speed_kmh = (
            (signal.trajectory.speed_kmh if signal.trajectory and signal.trajectory.speed_kmh else None)
            or cfg.speeds_kmh.get(signal.threat_type, 250.0)
        )
        time_to_impact = estimate_time_to_target(threat_coord, target.centroid, speed_kmh)
    else:
        # Check if any detected location matches monitored places
        matched_location = False
        for loc in signal.detected_locations:
            if any(loc.lower() in place.lower() for place in target.monitored_places):
                matched_location = True
                break

        if matched_location:
            dist_factor = 0.95
            distance_km = target.radius_km * 0.8
        else:
            # Check if this threat mentions distant regions (outside target sphere)
            is_distant_oblast = any(
                oblast in (signal.raw_text or "").lower()
                for oblast in (
                    "київ", "чернігів", "сумщин", "суми", "житомир", "полтав",
                    "харків", "дніпр", "запоріж", "волин", "рівнен", "львів",
                    "хмельницьк", "тернопіль", "франківськ", "закарпат", "чернівц", "донецьк", "луганськ"
                )
            )
            has_southern_marker = any(
                s in (signal.raw_text or "").lower()
                for s in (
                    "одес", "чорномор", "миколаїв", "крим", "море", "очаків",
                    "таїров", "рені", "ізмаїл", "дунай", "півд", "тузли", "курортн", "дністровськ"
                )
            )
            if is_distant_oblast and not has_southern_marker:
                dist_factor = 0.01  # Irrelevant distant northern/eastern threat
            else:
                dist_factor = cfg.unknown_coord_distance_factor

        # If heading towards target district is specified
        if signal.target_heading and any(w in signal.target_heading.lower() for w in ("одес", target.name.lower())):
            heading_factor = 1.0
            dist_factor = max(dist_factor, 0.85)
        else:
            heading_factor = 0.50

        if signal.threat_type == ThreatType.BALLISTIC:
            heading_factor = 1.0
            dist_factor = max(dist_factor, 0.98)

    # 4. Swarm quantity multiplier
    swarm_mult = calculate_swarm_multiplier(
        quantity=signal.quantity,
        factor=cfg.swarm_factor,
        max_multiplier=cfg.max_swarm_multiplier,
    )

    # Raw probability before temporal and spatial decay
    raw_p = min(0.99, base_weight * swarm_mult)

    # Combined decayed probability
    alignment_val = heading_factor if heading_factor is not None else 0.50
    decayed_p = base_weight * dist_factor * alignment_val * temporal_factor * swarm_mult
    decayed_p = max(0.0, min(0.99, decayed_p))

    desc_parts = [f"{signal.threat_type.value}"]
    if signal.quantity > 1:
        desc_parts.append(f"x{signal.quantity}")
    if distance_km is not None:
        desc_parts.append(f"at {distance_km:.1f} km")
    if time_to_impact is not None and not math.isinf(time_to_impact):
        desc_parts.append(f"ETA ~{time_to_impact:.0f}m")

    description = " ".join(desc_parts)

    return ThreatContribution(
        threat_id=signal.threat_id,
        threat_type=signal.threat_type,
        raw_probability=raw_p,
        decayed_probability=decayed_p,
        distance_km=distance_km,
        heading_factor=heading_factor,
        time_to_impact_minutes=time_to_impact if (time_to_impact and not math.isinf(time_to_impact)) else None,
        description=description,
    )


def calculate_aggregate_probability(
    signals: List[ThreatSignal],
    target: TargetPreset,
    current_time: Optional[datetime] = None,
    config: Optional[ScoringConfig] = None,
    reference_time: Optional[datetime] = None,
) -> ProbabilityResult:
    """Compute the multi-threat aggregate probability for the target preset.

    Steps:
    1. Filter out cancelled threats or neutralize threats cancelled by all-clear / type cancellation.
    2. Compute individual ThreatContribution for each remaining active signal.
    3. Apply probabilistic union: P_total = 1 - prod(1 - P_i).
    4. Determine AlertLevel from probability percent.
    5. Identify primary threat type and earliest time-to-impact.
    6. Generate comprehensive diagnostic summary.
    """
    cfg = config or DEFAULT_SCORING_CONFIG
    now = current_time or reference_time or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if not signals:
        return ProbabilityResult(
            target_district=target.name,
            probability_percent=0,
            alert_level=AlertLevel.GREEN,
            active_threat_count=0,
            primary_threat_type=None,
            estimated_time_to_impact_minutes=None,
            contributing_threats=[],
            summary="No active threats detected. Airspace is calm.",
            calculated_at=now,
        )

    # Separate cancellations and threats
    cancellations: List[ThreatSignal] = []
    active_candidates: List[ThreatSignal] = []

    for sig in signals:
        if sig.is_cancellation:
            cancellations.append(sig)
        else:
            active_candidates.append(sig)

    # Process cancellations:
    # If a cancellation exists with threat_type == UNKNOWN, it acts as an all-clear for all preceding signals
    # If a cancellation has a specific threat_type, it cancels preceding signals of that threat_type.
    filtered_signals: List[ThreatSignal] = []
    for sig in active_candidates:
        sig_cancelled = False
        for c in cancellations:
            # Cancellation must have occurred at or after the threat signal
            if c.timestamp >= sig.timestamp:
                if c.threat_type == ThreatType.UNKNOWN or c.threat_type == sig.threat_type:
                    sig_cancelled = True
                    break
        if not sig_cancelled:
            filtered_signals.append(sig)

    # Calculate individual contributions
    contributions: List[ThreatContribution] = []
    for sig in filtered_signals:
        contrib = calculate_threat_probability(sig, target, current_time=now, config=cfg)
        # Keep non-zero contributions
        if contrib.decayed_probability > 0.001:
            contributions.append(contrib)

    if not contributions:
        return ProbabilityResult(
            target_district=target.name,
            probability_percent=0,
            alert_level=AlertLevel.GREEN,
            active_threat_count=0,
            primary_threat_type=None,
            estimated_time_to_impact_minutes=None,
            contributing_threats=[],
            summary="All threats cleared or expired. District alert status GREEN.",
            calculated_at=now,
        )

    # Probabilistic union: P_total = 1 - prod(1 - P_i)
    prob_no_threat = 1.0
    for c in contributions:
        prob_no_threat *= (1.0 - c.decayed_probability)

    total_prob = 1.0 - prob_no_threat
    total_percent = int(round(total_prob * 100.0))
    total_percent = max(0, min(100, total_percent))

    # Determine alert level
    alert_level = AlertLevel.from_probability(total_percent)

    # Primary threat is the one with highest decayed probability
    sorted_contribs = sorted(contributions, key=lambda c: c.decayed_probability, reverse=True)
    primary_threat = sorted_contribs[0].threat_type if sorted_contribs else None

    # Earliest time to impact among inbound threats with valid ETA
    valid_etas = [
        c.time_to_impact_minutes
        for c in contributions
        if c.time_to_impact_minutes is not None and c.time_to_impact_minutes > 0.0
    ]
    min_eta: Optional[int] = int(round(min(valid_etas))) if valid_etas else None

    # Format summary
    threat_summary_items = [f"{c.description} (p={c.decayed_probability:.2f})" for c in sorted_contribs[:3]]
    threat_text = ", ".join(threat_summary_items)
    if len(sorted_contribs) > 3:
        threat_text += f", +{len(sorted_contribs) - 3} more"

    eta_str = f", ETA: ~{min_eta} min" if min_eta is not None else ""
    summary = (
        f"{alert_level.value} Alert ({total_percent}%): {len(contributions)} active threat track(s) "
        f"for {target.name}. Primary: {primary_threat.value if primary_threat else 'NONE'}{eta_str}. "
        f"Contributions: [{threat_text}]."
    )

    return ProbabilityResult(
        target_district=target.name,
        probability_percent=total_percent,
        alert_level=alert_level,
        active_threat_count=len(contributions),
        primary_threat_type=primary_threat,
        estimated_time_to_impact_minutes=min_eta,
        contributing_threats=contributions,
        summary=summary,
        calculated_at=now,
    )
