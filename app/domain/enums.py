"""Pure domain enumeration types and military threat taxonomy.

Zero external dependencies.
"""

from __future__ import annotations

from enum import Enum
from typing import Union


class ThreatType(str, Enum):
    """Canonical classification of aerial threats targeting Ukrainian airspace."""

    SHAHED = "SHAHED"
    BALLISTIC = "BALLISTIC"
    CRUISE_MISSILE = "CRUISE_MISSILE"
    TACTICAL_AVIATION = "TACTICAL_AVIATION"
    RECON_DRONE = "RECON_DRONE"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_str(cls, value: Union[str, ThreatType]) -> ThreatType:
        """Parse string to ThreatType safely with case-insensitivity."""
        if isinstance(value, cls):
            return value
        cleaned = str(value).strip().upper().replace(" ", "_").replace("-", "_")
        try:
            return cls(cleaned)
        except ValueError:
            return cls.UNKNOWN

    def __str__(self) -> str:
        return self.value


class AlertLevel(str, Enum):
    """Four-tier risk classification according to calculated probability thresholds."""

    GREEN = "GREEN"      # 0% - 24%: Low / Routine background vigilance
    YELLOW = "YELLOW"    # 25% - 49%: Moderate / Distant or ambiguous threat
    ORANGE = "ORANGE"    # 50% - 74%: High / Inbound threat heading towards perimeter
    RED = "RED"          # 75% - 100%: Severe / Imminent strike or direct approach

    @classmethod
    def from_probability(cls, prob_percent: float) -> AlertLevel:
        """Map percentage probability [0.0, 100.0] to AlertLevel.

        Thresholds:
        - 0.0 <= p < 25.0: GREEN
        - 25.0 <= p < 50.0: YELLOW
        - 50.0 <= p < 75.0: ORANGE
        - 75.0 <= p <= 100.0: RED
        """
        p = max(0.0, min(100.0, float(prob_percent)))
        if p < 25.0:
            return cls.GREEN
        elif p < 50.0:
            return cls.YELLOW
        elif p < 75.0:
            return cls.ORANGE
        else:
            return cls.RED

    def __str__(self) -> str:
        return self.value


class MovementSpeedClass(float, Enum):
    """Nominal operational ground speeds in km/h for aerial threats."""

    SHAHED = 185.0              # Shahed-136 cruise speed ~185 km/h
    BALLISTIC = 4000.0          # Iskander-M / Kinzhal hypersonic/ballistic profile
    CRUISE_MISSILE = 850.0      # Kalibr / Kh-101 subsonic cruise speed
    TACTICAL_AVIATION = 900.0   # Su-34/Su-35 air transit speed
    RECON_DRONE = 120.0         # Orlan-10 / ZALA / Supercam recon loiter speed
    UNKNOWN = 250.0             # Conservative fallback speed

    @classmethod
    def get_speed_for_threat(cls, threat_type: Union[ThreatType, str]) -> float:
        """Retrieve estimated speed in km/h for a given ThreatType."""
        tt = ThreatType.from_str(threat_type)
        mapping = {
            ThreatType.SHAHED: cls.SHAHED.value,
            ThreatType.BALLISTIC: cls.BALLISTIC.value,
            ThreatType.CRUISE_MISSILE: cls.CRUISE_MISSILE.value,
            ThreatType.TACTICAL_AVIATION: cls.TACTICAL_AVIATION.value,
            ThreatType.RECON_DRONE: cls.RECON_DRONE.value,
            ThreatType.UNKNOWN: cls.UNKNOWN.value,
        }
        return mapping.get(tt, cls.UNKNOWN.value)
