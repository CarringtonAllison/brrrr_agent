"""Tests for rental estimator — median calc, IQR outlier removal, fallback."""

from __future__ import annotations

import pytest
from datetime import date, timedelta

from backend.rental_estimator import (
    remove_outliers_iqr,
    estimate_rent_from_listings,
    estimate_rent_fallback,
    estimate_rent,
    RentalEstimate,
)


def make_rental(price: float, beds: int = 3, sqft: int = 1200) -> dict:
    return {
        "price": price,
        "beds": beds,
        "sqft": sqft,
        "listing_type": "rental",
        "scraped_at": date.today().isoformat(),
    }


# ── remove_outliers_iqr ───────────────────────────────────────────────────────

class TestRemoveOutliersIQR:
    def test_removes_extreme_high(self):
        prices = [800, 850, 900, 850, 875, 5000]  # 5000 is an outlier
        filtered = remove_outliers_iqr(prices)
        assert 5000 not in filtered

    def test_removes_extreme_low(self):
        prices = [800, 850, 900, 850, 875, 50]  # 50 is outlier
        filtered = remove_outliers_iqr(prices)
        assert 50 not in filtered

    def test_retains_normal_range(self):
        prices = [800, 850, 900, 875, 825]
        filtered = remove_outliers_iqr(prices)
        assert len(filtered) == 5

    def test_empty_input(self):
        assert remove_outliers_iqr([]) == []

    def test_single_value(self):
        assert remove_outliers_iqr([900]) == [900]

    def test_two_values_no_removal(self):
        result = remove_outliers_iqr([800, 900])
        assert len(result) == 2

    def test_returns_list(self):
        assert isinstance(remove_outliers_iqr([800, 850, 900]), list)


# ── estimate_rent_from_listings ───────────────────────────────────────────────

class TestEstimateRentFromListings:
    def _listings(self, prices: list[float], beds: int = 3) -> list[dict]:
        return [make_rental(p, beds=beds) for p in prices]

    def test_returns_median(self):
        rentals = self._listings([800, 900, 1000, 1100, 1200])
        result = estimate_rent_from_listings(rentals, target_beds=3)
        assert result == pytest.approx(1000.0)

    def test_filters_by_beds(self):
        """Only include rentals matching target bed count ±1."""
        rentals = [
            make_rental(800, beds=1),
            make_rental(1000, beds=3),
            make_rental(1050, beds=3),
            make_rental(1100, beds=3),
            make_rental(2000, beds=5),
        ]
        result = estimate_rent_from_listings(rentals, target_beds=3)
        assert result == pytest.approx(1050.0)

    def test_includes_adjacent_beds(self):
        """Beds ±1 from target should be included if not enough exact matches."""
        rentals = [
            make_rental(900, beds=2),
            make_rental(1000, beds=3),
            make_rental(1100, beds=4),
        ]
        result = estimate_rent_from_listings(rentals, target_beds=3)
        assert result is not None
        assert 900 <= result <= 1100

    def test_outliers_removed(self):
        """Extreme outliers should not skew the median significantly."""
        rentals = self._listings([900, 950, 1000, 1050, 1100, 10_000])
        result = estimate_rent_from_listings(rentals, target_beds=3)
        assert result < 5000

    def test_returns_none_when_no_matching_rentals(self):
        rentals = [make_rental(1000, beds=5)]
        result = estimate_rent_from_listings(rentals, target_beds=1)
        assert result is None

    def test_empty_input(self):
        assert estimate_rent_from_listings([], target_beds=3) is None


# ── estimate_rent_fallback ────────────────────────────────────────────────────

class TestEstimateRentFallback:
    def test_fallback_uses_1_1_percent_rule(self):
        """Fallback: 1.1% of ARV per month (the '1% rule' variant for BRRRR)."""
        arv = 100_000
        result = estimate_rent_fallback(arv)
        expected = arv * 0.011
        assert result == pytest.approx(expected)

    def test_fallback_with_zero_arv(self):
        assert estimate_rent_fallback(0) == pytest.approx(0.0)

    def test_fallback_returns_monthly_rent(self):
        result = estimate_rent_fallback(120_000)
        assert 500 < result < 2000  # sanity: reasonable range


# ── estimate_rent (full pipeline) ────────────────────────────────────────────

class TestEstimateRent:
    def _rentals(self, prices: list[float]) -> list[dict]:
        return [make_rental(p) for p in prices]

    def test_uses_market_data_when_available(self):
        rentals = self._rentals([900, 950, 1000, 1050, 1100])
        result = estimate_rent(rentals, target_beds=3, arv=100_000)
        assert isinstance(result, RentalEstimate)
        assert result.estimated_rent == pytest.approx(1000.0)
        assert result.source == "market"

    def test_falls_back_to_arv_rule_when_no_data(self):
        result = estimate_rent([], target_beds=3, arv=100_000)
        assert isinstance(result, RentalEstimate)
        assert result.source == "fallback"
        assert result.estimated_rent == pytest.approx(100_000 * 0.011)

    def test_sample_count_reflects_used_listings(self):
        rentals = self._rentals([900, 1000, 1100])
        result = estimate_rent(rentals, target_beds=3, arv=90_000)
        assert result.sample_count == 3

    def test_zero_sample_count_on_fallback(self):
        result = estimate_rent([], target_beds=3, arv=90_000)
        assert result.sample_count == 0

    def test_rent_estimate_is_positive(self):
        rentals = self._rentals([900, 1000, 1100])
        result = estimate_rent(rentals, target_beds=3, arv=90_000)
        assert result.estimated_rent > 0

    def test_fallback_when_no_arv(self):
        """Without ARV and without rentals, fallback should return None rent."""
        result = estimate_rent([], target_beds=3, arv=None)
        assert result.estimated_rent is None
        assert result.source == "none"
