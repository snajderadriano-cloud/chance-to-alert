"""Domain layer package for Chance to Alert.App.

Contains pure Python entities, threat taxonomy enums, spatial geometry,
and threat probability scoring engine. Zero external framework dependencies.
"""

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
    ScoringConfig,
    calculate_aggregate_probability,
    calculate_threat_probability,
)

__all__ = [
    # Enums
    "ThreatType",
    "AlertLevel",
    "MovementSpeedClass",
    # Entities
    "GeoCoordinate",
    "TargetPreset",
    "TrajectoryVector",
    "ThreatSignal",
    "ThreatContribution",
    "ProbabilityResult",
    # Geo math
    "haversine_distance",
    "calculate_azimuth",
    "bearing_difference",
    "is_heading_towards_target",
    "calculate_heading_alignment_factor",
    "estimate_time_to_target",
    # Scoring
    "ScoringConfig",
    "calculate_threat_probability",
    "calculate_aggregate_probability",
]
