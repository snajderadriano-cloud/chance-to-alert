"""Unit test suite for app.domain.geo (spatial geometry, Haversine, azimuth, vector heading)."""

import math
import pytest

from app.domain.entities import GeoCoordinate
from app.domain.geo import (
    bearing_difference,
    calculate_azimuth,
    calculate_heading_alignment_factor,
    estimate_time_to_target,
    haversine_distance,
    is_heading_towards_target,
)


class TestGeoCoordinate:
    """Tests for GeoCoordinate validation and representation."""

    def test_valid_coordinates(self) -> None:
        c1 = GeoCoordinate(lat=46.4825, lon=30.7233)
        assert c1.lat == 46.4825
        assert c1.lon == 30.7233
        assert c1.as_tuple() == (46.4825, 30.7233)

    def test_boundary_values(self) -> None:
        c_north_pole = GeoCoordinate(lat=90.0, lon=0.0)
        c_south_pole = GeoCoordinate(lat=-90.0, lon=0.0)
        c_date_line_east = GeoCoordinate(lat=0.0, lon=180.0)
        c_date_line_west = GeoCoordinate(lat=0.0, lon=-180.0)
        assert c_north_pole.lat == 90.0
        assert c_south_pole.lat == -90.0
        assert c_date_line_east.lon == 180.0
        assert c_date_line_west.lon == -180.0

    def test_invalid_latitude_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Latitude must be between -90.0 and 90.0"):
            GeoCoordinate(lat=90.01, lon=30.0)

        with pytest.raises(ValueError, match="Latitude must be between -90.0 and 90.0"):
            GeoCoordinate(lat=-90.1, lon=30.0)

    def test_invalid_longitude_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Longitude must be between -180.0 and 180.0"):
            GeoCoordinate(lat=46.0, lon=180.01)

        with pytest.raises(ValueError, match="Longitude must be between -180.0 and 180.0"):
            GeoCoordinate(lat=46.0, lon=-180.5)

    def test_dict_serialization(self) -> None:
        coord = GeoCoordinate(lat=46.4825, lon=30.7233)
        d = coord.to_dict()
        assert d == {"lat": 46.4825, "lon": 30.7233}
        reconstructed = GeoCoordinate.from_dict(d)
        assert reconstructed == coord

    def test_dict_deserialization_missing_keys(self) -> None:
        with pytest.raises(KeyError):
            GeoCoordinate.from_dict({"lat": 46.0})


class TestHaversineDistance:
    """Tests for Haversine great-circle distance calculation."""

    def test_distance_same_point(self) -> None:
        c = GeoCoordinate(lat=46.4825, lon=30.7233)
        assert haversine_distance(c, c) == 0.0

    def test_distance_odesa_to_chornomorsk(self) -> None:
        # Odesa center to Chornomorsk center (~20-22 km)
        odesa = GeoCoordinate(lat=46.4825, lon=30.7233)
        chornomorsk = GeoCoordinate(lat=46.3015, lon=30.6559)
        d = haversine_distance(odesa, chornomorsk)
        assert 20.0 < d < 22.0

    def test_distance_odesa_to_mykolaiv(self) -> None:
        # Odesa to Mykolaiv (~110-115 km)
        odesa = GeoCoordinate(lat=46.4825, lon=30.7233)
        mykolaiv = GeoCoordinate(lat=46.9750, lon=31.9946)
        d = haversine_distance(odesa, mykolaiv)
        assert 110.0 < d < 120.0

    def test_distance_odesa_to_kyiv(self) -> None:
        # Odesa to Kyiv (~440-445 km)
        odesa = GeoCoordinate(lat=46.4825, lon=30.7233)
        kyiv = GeoCoordinate(lat=50.4501, lon=30.5234)
        d = haversine_distance(odesa, kyiv)
        assert 435.0 < d < 450.0

    def test_distance_symmetry(self) -> None:
        c1 = GeoCoordinate(lat=46.4825, lon=30.7233)
        c2 = GeoCoordinate(lat=46.9750, lon=31.9946)
        assert math.isclose(haversine_distance(c1, c2), haversine_distance(c2, c1), rel_tol=1e-9)

    def test_distance_equator_one_degree(self) -> None:
        # 1 degree of longitude at equator is ~111.19 km (6371 * pi / 180)
        c1 = GeoCoordinate(lat=0.0, lon=0.0)
        c2 = GeoCoordinate(lat=0.0, lon=1.0)
        d = haversine_distance(c1, c2)
        assert 111.0 < d < 112.0


class TestCalculateAzimuth:
    """Tests for initial bearing / forward azimuth calculation."""

    def test_identical_points_returns_zero(self) -> None:
        c = GeoCoordinate(lat=46.4825, lon=30.7233)
        assert calculate_azimuth(c, c) == 0.0

    def test_cardinal_directions_from_equator(self) -> None:
        origin = GeoCoordinate(lat=0.0, lon=0.0)
        north = GeoCoordinate(lat=10.0, lon=0.0)
        south = GeoCoordinate(lat=-10.0, lon=0.0)
        east = GeoCoordinate(lat=0.0, lon=10.0)
        west = GeoCoordinate(lat=0.0, lon=-10.0)

        assert math.isclose(calculate_azimuth(origin, north), 0.0, abs_tol=1e-5)
        assert math.isclose(calculate_azimuth(origin, east), 90.0, abs_tol=1e-5)
        assert math.isclose(calculate_azimuth(origin, south), 180.0, abs_tol=1e-5)
        assert math.isclose(calculate_azimuth(origin, west), 270.0, abs_tol=1e-5)

    def test_bearing_black_sea_to_odesa(self) -> None:
        # Approaching from south (Cape Fountain / Black sea) directly north to Odesa
        sea_point = GeoCoordinate(lat=45.5000, lon=30.7233)
        odesa = GeoCoordinate(lat=46.4825, lon=30.7233)
        bearing = calculate_azimuth(sea_point, odesa)
        # Meridian aligned heading straight north
        assert math.isclose(bearing, 0.0, abs_tol=0.1)

    def test_bearing_mykolaiv_to_odesa(self) -> None:
        # Mykolaiv (NE) towards Odesa (SW): bearing should be in 230°-245° range
        mykolaiv = GeoCoordinate(lat=46.9750, lon=31.9946)
        odesa = GeoCoordinate(lat=46.4825, lon=30.7233)
        bearing = calculate_azimuth(mykolaiv, odesa)
        assert 230.0 < bearing < 245.0


class TestBearingDifference:
    """Tests for minimum angular difference between bearings."""

    def test_identical_bearings(self) -> None:
        assert bearing_difference(0.0, 0.0) == 0.0
        assert bearing_difference(180.0, 180.0) == 0.0
        assert bearing_difference(270.0, 270.0) == 0.0

    def test_small_differences(self) -> None:
        assert bearing_difference(10.0, 25.0) == 15.0
        assert bearing_difference(25.0, 10.0) == 15.0

    def test_wrap_around_zero(self) -> None:
        # 350° and 10° have an angular difference of 20°
        assert bearing_difference(350.0, 10.0) == 20.0
        assert bearing_difference(10.0, 350.0) == 20.0
        assert bearing_difference(355.0, 5.0) == 10.0

    def test_opposite_bearings(self) -> None:
        assert bearing_difference(0.0, 180.0) == 180.0
        assert bearing_difference(90.0, 270.0) == 180.0
        assert bearing_difference(270.0, 90.0) == 180.0

    def test_modulo_normalization(self) -> None:
        # Inputs beyond 360 should normalize
        assert bearing_difference(370.0, 10.0) == 0.0
        assert bearing_difference(720.0, 180.0) == 180.0


class TestHeadingAlignmentAndDetection:
    """Tests for vector heading alignment and target heading checks."""

    def test_is_heading_towards_target_direct(self) -> None:
        threat = GeoCoordinate(lat=45.5, lon=30.7233)
        target = GeoCoordinate(lat=46.4825, lon=30.7233)
        # Threat is south of target, heading 0° (North) -> directly heading to target
        assert is_heading_towards_target(threat, heading_degrees=0.0, target_coord=target) is True
        assert is_heading_towards_target(threat, heading_degrees=15.0, target_coord=target) is True
        assert is_heading_towards_target(threat, heading_degrees=44.0, target_coord=target) is True

    def test_is_heading_towards_target_away(self) -> None:
        threat = GeoCoordinate(lat=45.5, lon=30.7233)
        target = GeoCoordinate(lat=46.4825, lon=30.7233)
        # Heading 180° (South, away into Black Sea)
        assert is_heading_towards_target(threat, heading_degrees=180.0, target_coord=target) is False
        assert is_heading_towards_target(threat, heading_degrees=90.0, target_coord=target) is False

    def test_heading_tolerance_boundary(self) -> None:
        threat = GeoCoordinate(lat=45.5, lon=30.7233)
        target = GeoCoordinate(lat=46.4825, lon=30.7233)
        # Azimuth is ~0.0 deg. With tolerance 45.0:
        assert is_heading_towards_target(threat, 45.0, target, tolerance_degrees=45.0) is True
        assert is_heading_towards_target(threat, 45.1, target, tolerance_degrees=45.0) is False

    def test_heading_alignment_factor_values(self) -> None:
        threat = GeoCoordinate(lat=45.5, lon=30.7233)
        target = GeoCoordinate(lat=46.4825, lon=30.7233)

        # 0° offset -> factor 1.0
        f_direct = calculate_heading_alignment_factor(threat, 0.0, target)
        assert math.isclose(f_direct, 1.0, abs_tol=1e-3)

        # 90° offset -> perpendicular -> factor 0.25
        f_perp = calculate_heading_alignment_factor(threat, 90.0, target)
        assert math.isclose(f_perp, 0.25, abs_tol=1e-3)

        # 180° offset -> opposite -> factor 0.0
        f_away = calculate_heading_alignment_factor(threat, 180.0, target)
        assert math.isclose(f_away, 0.0, abs_tol=1e-3)

        # None heading -> default uncertainty factor 0.50
        f_none = calculate_heading_alignment_factor(threat, None, target)
        assert f_none == 0.50

    def test_heading_alignment_factor_monotonicity(self) -> None:
        threat = GeoCoordinate(lat=45.5, lon=30.7233)
        target = GeoCoordinate(lat=46.4825, lon=30.7233)
        # As heading drifts from 0° (direct) to 180° (opposite), factor must strictly decrease
        angles = [0.0, 15.0, 30.0, 45.0, 60.0, 90.0, 120.0, 150.0, 180.0]
        factors = [calculate_heading_alignment_factor(threat, a, target) for a in angles]
        for i in range(len(factors) - 1):
            assert factors[i] >= factors[i + 1]


class TestEstimateTimeToTarget:
    """Tests for kinematic time-to-target calculations."""

    def test_basic_speed_calculation(self) -> None:
        # Distance 100 km at 200 km/h = 30 minutes
        # Construct two points ~111.19 km apart (1 deg lat)
        c1 = GeoCoordinate(lat=0.0, lon=0.0)
        c2 = GeoCoordinate(lat=1.0, lon=0.0)
        d = haversine_distance(c1, c2)
        eta_minutes = estimate_time_to_target(c1, c2, speed_kmh=d)  # at speed=distance, time is 1 hour = 60 min
        assert math.isclose(eta_minutes, 60.0, rel_tol=1e-3)

    def test_at_target_returns_zero(self) -> None:
        c = GeoCoordinate(lat=46.4825, lon=30.7233)
        assert estimate_time_to_target(c, c, speed_kmh=185.0) == 0.0

    def test_non_positive_speed_returns_inf(self) -> None:
        c1 = GeoCoordinate(lat=46.4825, lon=30.7233)
        c2 = GeoCoordinate(lat=46.9750, lon=31.9946)
        assert math.isinf(estimate_time_to_target(c1, c2, speed_kmh=0.0))
        assert math.isinf(estimate_time_to_target(c1, c2, speed_kmh=-50.0))

    def test_shahed_speed_eta(self) -> None:
        # Threat 92.5 km away at 185 km/h -> exactly 30 minutes
        c1 = GeoCoordinate(lat=45.65, lon=30.7233)
        c2 = GeoCoordinate(lat=46.4825, lon=30.7233)
        d = haversine_distance(c1, c2)
        eta = estimate_time_to_target(c1, c2, speed_kmh=185.0)
        expected_eta = (d / 185.0) * 60.0
        assert math.isclose(eta, expected_eta, rel_tol=1e-4)
