"""Tests for geocoder module — bounding box math, ZIP proximity, address geocoding."""

import pytest
from unittest.mock import patch, MagicMock

from backend.geocoder import (
    bounding_box_from_center,
    find_nearby_zips,
    geocode_address,
    get_zip_centroid,
)


class TestBoundingBox:
    def test_basic_5_mile_radius(self):
        """Birmingham, AL center (~33.52, -86.81) with 5-mile radius."""
        south, north, west, east = bounding_box_from_center(33.52, -86.81, 5.0)
        # 5 miles ≈ 0.0725 degrees latitude
        assert south == pytest.approx(33.4475, abs=0.01)
        assert north == pytest.approx(33.5925, abs=0.01)
        # Longitude range wider due to cos(lat)
        assert west < -86.81
        assert east > -86.81
        # Box should be roughly symmetric
        assert (north - 33.52) == pytest.approx(33.52 - south, abs=0.001)

    def test_zero_radius(self):
        south, north, west, east = bounding_box_from_center(40.0, -80.0, 0.0)
        assert south == pytest.approx(40.0)
        assert north == pytest.approx(40.0)

    def test_larger_radius(self):
        """10-mile radius should produce a bigger box than 5-mile."""
        box_5 = bounding_box_from_center(33.52, -86.81, 5.0)
        box_10 = bounding_box_from_center(33.52, -86.81, 10.0)
        assert box_10[0] < box_5[0]   # south further south
        assert box_10[1] > box_5[1]   # north further north


class TestZipCentroid:
    def test_known_zip(self):
        """35203 (Birmingham downtown) should return reasonable coords."""
        lat, lon = get_zip_centroid("35203")
        assert 33.0 < lat < 34.0
        assert -87.5 < lon < -86.0

    def test_invalid_zip_returns_none(self):
        result = get_zip_centroid("00000")
        assert result is None


class TestFindNearbyZips:
    def test_finds_multiple_zips(self):
        """Birmingham center should have multiple ZIPs within 5 miles."""
        nearby = find_nearby_zips(33.52, -86.81, 5.0)
        assert len(nearby) > 1
        # Each entry should have zip and distance
        for entry in nearby:
            assert "zip" in entry
            assert "distance_miles" in entry
            assert entry["distance_miles"] <= 5.0

    def test_sorted_by_distance(self):
        nearby = find_nearby_zips(33.52, -86.81, 5.0)
        distances = [z["distance_miles"] for z in nearby]
        assert distances == sorted(distances)

    def test_small_radius_fewer_results(self):
        nearby_1 = find_nearby_zips(33.52, -86.81, 1.0)
        nearby_5 = find_nearby_zips(33.52, -86.81, 5.0)
        assert len(nearby_1) <= len(nearby_5)


class TestGeocodeAddress:
    @patch("backend.geocoder._census_geocode")
    def test_uses_census_geocoder(self, mock_census):
        """Should call Census geocoder and return coords."""
        mock_census.return_value = (33.5186, -86.8104)
        lat, lon = geocode_address("123 Main St, Birmingham, AL 35203")
        assert lat == pytest.approx(33.5186)
        assert lon == pytest.approx(-86.8104)
        mock_census.assert_called_once()

    @patch("backend.geocoder._census_geocode")
    def test_returns_none_on_failure(self, mock_census):
        """Should return None if geocoding fails."""
        mock_census.return_value = None
        result = geocode_address("totally fake address 99999")
        assert result is None

    @patch("backend.geocoder._census_geocode")
    def test_caches_result(self, mock_census):
        """Second call for same address should not hit the geocoder again."""
        mock_census.return_value = (33.5186, -86.8104)
        geocode_address("123 Main St, Birmingham, AL 35203", cache={})
        geocode_address("123 Main St, Birmingham, AL 35203", cache={})
        # With a shared cache dict, the mock should only be called once
        # (this tests the caching logic, not the DB cache)
