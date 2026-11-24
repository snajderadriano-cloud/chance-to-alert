"""Spatial geometry and vector heading calculation engine.

Provides geodetic calculations: Haversine distance, forward azimuth (bearing),
angular delta, heading alignment factors, and kinematic time-to-target estimations.
Zero external framework dependencies.
"""

from __future__ import annotations

import math
from typing import Optional

from app.domain.entities import GeoCoordinate

# Standard WGS84 mean earth radius in kilometers
EARTH_RADIUS_KM: float = 6371.0


def haversine_distance(coord1: GeoCoordinate, coord2: GeoCoordinate) -> float:
    """Calculate the great-circle distance between two coordinates in kilometers.

    Uses the Haversine formula with numerical stability clamping.
    """
    if coord1.lat == coord2.lat and coord1.lon == coord2.lon:
        return 0.0

    lat1_rad = math.radians(coord1.lat)
    lon1_rad = math.radians(coord1.lon)
    lat2_rad = math.radians(coord2.lat)
    lon2_rad = math.radians(coord2.lon)

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    sin_half_lat = math.sin(delta_lat / 2.0)
    sin_half_lon = math.sin(delta_lon / 2.0)

    a = (
        sin_half_lat * sin_half_lat
        + math.cos(lat1_rad) * math.cos(lat2_rad) * sin_half_lon * sin_half_lon
    )
    # Clamp to avoid floating point precision overflow outside [0.0, 1.0]
    a = max(0.0, min(1.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return EARTH_RADIUS_KM * c


def calculate_azimuth(coord1: GeoCoordinate, coord2: GeoCoordinate) -> float:
    """Calculate initial bearing / forward azimuth from coord1 to coord2 in degrees.

    Returns bearing in the range [0.0, 360.0).
    Bearing 0 = North, 90 = East, 180 = South, 270 = West.
    If coord1 and coord2 are identical, returns 0.0.
    """
    if coord1.lat == coord2.lat and coord1.lon == coord2.lon:
        return 0.0

    lat1_rad = math.radians(coord1.lat)
    lat2_rad = math.radians(coord2.lat)
    delta_lon = math.radians(coord2.lon - coord1.lon)

    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = (
        math.cos(lat1_rad) * math.sin(lat2_rad)
        - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
    )

    bearing_rad = math.atan2(y, x)
    bearing_deg = (math.degrees(bearing_rad) + 360.0) % 360.0

    return bearing_deg


def bearing_difference(bearing1: float, bearing2: float) -> float:
    """Calculate the minimum angular difference between two bearings in degrees.

    Returns value in range [0.0, 180.0].
    """
    b1 = float(bearing1) % 360.0
    b2 = float(bearing2) % 360.0
    diff = abs(b1 - b2) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return diff


def is_heading_towards_target(
    threat_coord: GeoCoordinate,
    heading_degrees: float,
    target_coord: GeoCoordinate,
    tolerance_degrees: float = 45.0,
) -> bool:
    """Determine whether a threat's heading vector points towards the target coordinate.

    Args:
        threat_coord: Current position of the threat.
        heading_degrees: Direction of movement in degrees [0, 360).
        target_coord: Centroid or location of the target area.
        tolerance_degrees: Angular cone tolerance (default 45 degrees).

    Returns:
        True if the threat vector points within tolerance of the target, False otherwise.
    """
    if threat_coord.lat == target_coord.lat and threat_coord.lon == target_coord.lon:
        return True

    target_bearing = calculate_azimuth(threat_coord, target_coord)
    diff = bearing_difference(heading_degrees, target_bearing)
    return diff <= tolerance_degrees


def calculate_heading_alignment_factor(
    threat_coord: GeoCoordinate,
    heading_degrees: Optional[float],
    target_coord: GeoCoordinate,
) -> float:
    """Calculate directional alignment factor between threat heading and target.

    Returns a factor in range [0.0, 1.0]:
    - 1.0: Threat is moving directly towards target centroid.
    - ~0.73: Heading is 45 degrees offset.
    - 0.25: Heading is 90 degrees offset (perpendicular).
    - 0.0: Threat is moving directly away (180 degrees offset).
    - If heading_degrees is None: returns default neutral factor (0.50).
    """
    if threat_coord.lat == target_coord.lat and threat_coord.lon == target_coord.lon:
        return 1.0

    if heading_degrees is None:
        return 0.50

    target_bearing = calculate_azimuth(threat_coord, target_coord)
    diff = bearing_difference(heading_degrees, target_bearing)

    # Smooth cosine-squared decay: ((1 + cos(theta)) / 2)^2
    diff_rad = math.radians(diff)
    cos_half = (1.0 + math.cos(diff_rad)) / 2.0
    factor = cos_half * cos_half

    return max(0.0, min(1.0, factor))


def estimate_time_to_target(
    threat_coord: GeoCoordinate,
    target_coord: GeoCoordinate,
    speed_kmh: float,
) -> float:
    """Estimate time in minutes required to reach the target coordinate at constant speed.

    Args:
        threat_coord: Starting or current coordinate.
        target_coord: Destination coordinate.
        speed_kmh: Ground speed in km/h.

    Returns:
        Estimated time in minutes. Returns 0.0 if at target, or float('inf') if speed <= 0.
    """
    distance_km = haversine_distance(threat_coord, target_coord)
    if distance_km <= 0.001:
        return 0.0
    if speed_kmh <= 0.0:
        return float("inf")

    time_hours = distance_km / speed_kmh
    return time_hours * 60.0
