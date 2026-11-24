"""Pure domain entities for threat assessment and geographic calculations.

Zero external framework dependencies: relies only on Python standard library.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from app.domain.enums import AlertLevel, MovementSpeedClass, ThreatType


@dataclass(frozen=True)
class GeoCoordinate:
    """WGS84 geographic coordinate (latitude and longitude in decimal degrees)."""

    lat: float
    lon: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "lat", float(self.lat))
        object.__setattr__(self, "lon", float(self.lon))
        if not (-90.0 <= self.lat <= 90.0):
            raise ValueError(f"Latitude must be between -90.0 and 90.0 degrees, got {self.lat}")
        if not (-180.0 <= self.lon <= 180.0):
            raise ValueError(f"Longitude must be between -180.0 and 180.0 degrees, got {self.lon}")

    def as_tuple(self) -> Tuple[float, float]:
        """Return coordinate as (latitude, longitude) tuple."""
        return (self.lat, self.lon)

    def to_dict(self) -> Dict[str, float]:
        """Convert coordinate to dictionary representation."""
        return {"lat": self.lat, "lon": self.lon}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GeoCoordinate:
        """Create GeoCoordinate from dictionary with 'lat' and 'lon' keys."""
        if "lat" not in data or "lon" not in data:
            raise KeyError("Dictionary must contain 'lat' and 'lon' keys")
        return cls(lat=float(data["lat"]), lon=float(data["lon"]))


@dataclass
class TargetPreset:
    """Configured target district or oblast preset for threat assessment."""

    name: str
    centroid: GeoCoordinate
    radius_km: float
    zones: Dict[str, float] = field(default_factory=dict)
    monitored_places: List[str] = field(default_factory=list)
    warning_radius_km: float = 100.0
    transit_corridors: List[str] = field(default_factory=list)
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Target preset name cannot be empty")
        if self.radius_km <= 0.0:
            raise ValueError(f"Target preset radius_km must be positive, got {self.radius_km}")
        if self.warning_radius_km < self.radius_km:
            raise ValueError(
                f"Warning radius ({self.warning_radius_km} km) must be >= target radius ({self.radius_km} km)"
            )
        if isinstance(self.centroid, dict):
            self.centroid = GeoCoordinate.from_dict(self.centroid)

    def to_dict(self) -> Dict[str, Any]:
        """Convert preset to dictionary representation."""
        return {
            "name": self.name,
            "centroid": self.centroid.to_dict(),
            "radius_km": self.radius_km,
            "warning_radius_km": self.warning_radius_km,
            "zones": dict(self.zones),
            "monitored_places": list(self.monitored_places),
            "transit_corridors": list(self.transit_corridors),
            "description": self.description,
        }


@dataclass
class TrajectoryVector:
    """Estimated kinematic vector representing direction, speed, and location."""

    origin: Optional[GeoCoordinate] = None
    current: Optional[GeoCoordinate] = None
    heading_degrees: Optional[float] = None  # [0.0, 360.0) forward azimuth
    speed_kmh: Optional[float] = None        # Speed in km/h
    altitude_m: Optional[float] = None       # Altitude in meters

    def __post_init__(self) -> None:
        if self.heading_degrees is not None:
            self.heading_degrees = float(self.heading_degrees) % 360.0
        if self.speed_kmh is not None:
            self.speed_kmh = float(self.speed_kmh)
            if self.speed_kmh < 0.0:
                raise ValueError(f"Speed cannot be negative, got {self.speed_kmh}")
        if self.altitude_m is not None:
            self.altitude_m = float(self.altitude_m)
        if isinstance(self.origin, dict):
            self.origin = GeoCoordinate.from_dict(self.origin)
        if isinstance(self.current, dict):
            self.current = GeoCoordinate.from_dict(self.current)

    def to_dict(self) -> Dict[str, Any]:
        """Convert trajectory vector to dictionary representation."""
        return {
            "origin": self.origin.to_dict() if self.origin else None,
            "current": self.current.to_dict() if self.current else None,
            "heading_degrees": self.heading_degrees,
            "speed_kmh": self.speed_kmh,
            "altitude_m": self.altitude_m,
        }


@dataclass
class ThreatSignal:
    """Parsed operational intelligence signal indicating potential aerial activity."""

    threat_type: ThreatType
    quantity: int = 1
    raw_text: str = ""
    source_channel: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    origin_location: Optional[str] = None
    target_heading: Optional[str] = None
    detected_locations: List[str] = field(default_factory=list)
    current_coordinate: Optional[GeoCoordinate] = None
    trajectory: Optional[TrajectoryVector] = None
    is_cancellation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    threat_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.threat_type, ThreatType):
            self.threat_type = ThreatType.from_str(self.threat_type)
        if self.quantity < 1:
            self.quantity = 1
        if not self.threat_id:
            self.threat_id = str(uuid.uuid4())
        if isinstance(self.current_coordinate, dict):
            self.current_coordinate = GeoCoordinate.from_dict(self.current_coordinate)
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert threat signal to dictionary representation."""
        return {
            "threat_id": self.threat_id,
            "threat_type": self.threat_type.value,
            "quantity": self.quantity,
            "raw_text": self.raw_text,
            "source_channel": self.source_channel,
            "timestamp": self.timestamp.isoformat(),
            "origin_location": self.origin_location,
            "target_heading": self.target_heading,
            "detected_locations": list(self.detected_locations),
            "current_coordinate": self.current_coordinate.to_dict() if self.current_coordinate else None,
            "trajectory": self.trajectory.to_dict() if self.trajectory else None,
            "is_cancellation": self.is_cancellation,
            "metadata": dict(self.metadata),
        }


@dataclass
class ThreatContribution:
    """Individual threat contribution towards the aggregate district probability."""

    threat_id: str
    threat_type: ThreatType
    raw_probability: float               # [0.0, 1.0] before decay / swarm
    decayed_probability: float           # [0.0, 1.0] after temporal and spatial decay
    distance_km: Optional[float] = None
    heading_factor: Optional[float] = None
    time_to_impact_minutes: Optional[float] = None
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.threat_type, ThreatType):
            self.threat_type = ThreatType.from_str(self.threat_type)
        self.raw_probability = max(0.0, min(1.0, float(self.raw_probability)))
        self.decayed_probability = max(0.0, min(1.0, float(self.decayed_probability)))

    def to_dict(self) -> Dict[str, Any]:
        """Convert threat contribution to dictionary representation."""
        return {
            "threat_id": self.threat_id,
            "threat_type": self.threat_type.value,
            "raw_probability": round(self.raw_probability, 4),
            "decayed_probability": round(self.decayed_probability, 4),
            "distance_km": round(self.distance_km, 1) if self.distance_km is not None else None,
            "heading_factor": round(self.heading_factor, 3) if self.heading_factor is not None else None,
            "time_to_impact_minutes": round(self.time_to_impact_minutes, 1) if self.time_to_impact_minutes is not None else None,
            "description": self.description,
        }


@dataclass
class ProbabilityResult:
    """Aggregate alert probability calculation result for a target preset."""

    target_district: str
    probability_percent: int             # 0 to 100
    alert_level: AlertLevel
    active_threat_count: int
    primary_threat_type: Optional[ThreatType] = None
    estimated_time_to_impact_minutes: Optional[int] = None
    contributing_threats: List[ThreatContribution] = field(default_factory=list)
    summary: str = ""
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.probability_percent = max(0, min(100, int(round(self.probability_percent))))
        if not isinstance(self.alert_level, AlertLevel):
            self.alert_level = AlertLevel.from_probability(self.probability_percent)
        if self.primary_threat_type and not isinstance(self.primary_threat_type, ThreatType):
            self.primary_threat_type = ThreatType.from_str(self.primary_threat_type)
        if self.calculated_at.tzinfo is None:
            self.calculated_at = self.calculated_at.replace(tzinfo=timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert probability result to dictionary representation."""
        return {
            "target_district": self.target_district,
            "probability_percent": self.probability_percent,
            "alert_level": self.alert_level.value,
            "active_threat_count": self.active_threat_count,
            "primary_threat_type": self.primary_threat_type.value if self.primary_threat_type else None,
            "estimated_time_to_impact_minutes": self.estimated_time_to_impact_minutes,
            "contributing_threats": [t.to_dict() for t in self.contributing_threats],
            "summary": self.summary,
            "calculated_at": self.calculated_at.isoformat(),
        }
