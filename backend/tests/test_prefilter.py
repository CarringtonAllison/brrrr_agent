"""Tests for listing pre-filter.

Pre-filter runs before any analysis to eliminate obviously bad listings.
"""

import pytest

from backend.prefilter import apply_prefilter


def _make_listing(**overrides) -> dict:
    """Create a listing dict with sensible defaults, overridable per test."""
    base = {
        "price": 75_000,
        "beds": 3,
        "baths": 1.5,
        "sqft": 1_100,
        "property_type": "single family",
        "days_on_market": 30,
    }
    base.update(overrides)
    return base


class TestPriceFilter:
    def test_passes_within_range(self):
        passed, _ = apply_prefilter(_make_listing(price=75_000))
        assert passed is True

    def test_rejects_too_expensive(self):
        passed, reason = apply_prefilter(_make_listing(price=120_000))
        assert passed is False
        assert "price" in reason.lower()

    def test_rejects_too_cheap(self):
        passed, reason = apply_prefilter(_make_listing(price=20_000))
        assert passed is False
        assert "price" in reason.lower()

    def test_rejects_no_price(self):
        passed, reason = apply_prefilter(_make_listing(price=None))
        assert passed is False
        assert "price" in reason.lower()

    def test_boundary_min(self):
        passed, _ = apply_prefilter(_make_listing(price=25_000))
        assert passed is True

    def test_boundary_max(self):
        passed, _ = apply_prefilter(_make_listing(price=100_000))
        assert passed is True


class TestBedroomFilter:
    def test_passes_3_bed(self):
        passed, _ = apply_prefilter(_make_listing(beds=3))
        assert passed is True

    def test_rejects_1_bed(self):
        passed, reason = apply_prefilter(_make_listing(beds=1))
        assert passed is False
        assert "bed" in reason.lower()

    def test_rejects_6_bed(self):
        passed, reason = apply_prefilter(_make_listing(beds=6))
        assert passed is False
        assert "bed" in reason.lower()

    def test_boundary_2_bed(self):
        passed, _ = apply_prefilter(_make_listing(beds=2))
        assert passed is True

    def test_boundary_5_bed(self):
        passed, _ = apply_prefilter(_make_listing(beds=5))
        assert passed is True


class TestPropertyTypeFilter:
    def test_passes_single_family(self):
        passed, _ = apply_prefilter(_make_listing(property_type="single family"))
        assert passed is True

    def test_passes_townhouse(self):
        passed, _ = apply_prefilter(_make_listing(property_type="townhouse"))
        assert passed is True

    def test_rejects_condo(self):
        passed, reason = apply_prefilter(_make_listing(property_type="condo"))
        assert passed is False
        assert "type" in reason.lower()

    def test_rejects_land(self):
        passed, reason = apply_prefilter(_make_listing(property_type="land"))
        assert passed is False

    def test_case_insensitive(self):
        passed, _ = apply_prefilter(_make_listing(property_type="Single Family"))
        assert passed is True


class TestSqftFilter:
    def test_passes_1100(self):
        passed, _ = apply_prefilter(_make_listing(sqft=1_100))
        assert passed is True

    def test_rejects_too_small(self):
        passed, reason = apply_prefilter(_make_listing(sqft=500))
        assert passed is False
        assert "sqft" in reason.lower()

    def test_passes_no_sqft(self):
        """Missing sqft should pass — we don't reject unknowns."""
        passed, _ = apply_prefilter(_make_listing(sqft=None))
        assert passed is True

    def test_boundary_700(self):
        passed, _ = apply_prefilter(_make_listing(sqft=700))
        assert passed is True


class TestDaysOnMarketFilter:
    def test_passes_fresh(self):
        passed, _ = apply_prefilter(_make_listing(days_on_market=10))
        assert passed is True

    def test_rejects_stale(self):
        passed, reason = apply_prefilter(_make_listing(days_on_market=150))
        assert passed is False
        assert "days" in reason.lower() or "market" in reason.lower()

    def test_boundary_120(self):
        passed, _ = apply_prefilter(_make_listing(days_on_market=120))
        assert passed is True

    def test_passes_no_dom(self):
        """Missing DOM should pass — we don't reject unknowns."""
        passed, _ = apply_prefilter(_make_listing(days_on_market=None))
        assert passed is True
