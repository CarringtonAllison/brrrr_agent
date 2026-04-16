"""Tests for comp analyzer — tiered filtering, similarity scoring, ARV estimation."""

from __future__ import annotations

import pytest
from datetime import date, timedelta

from backend.comp_analyzer import (
    score_comp,
    is_distressed,
    filter_comps_tiered,
    estimate_arv,
    ARVEstimate,
)

# ── Helpers ─────────────────────────────────────────────────────────────────

def days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def make_comp(
    price: float = 80_000,
    sqft: int = 1200,
    beds: int = 3,
    baths: float = 1.0,
    distance_miles: float = 0.3,
    sold_days_ago: int = 60,
    source: str = "redfin",
    address: str = "123 Elm St",
    listing_type: str = "",
    description: str = "",
) -> dict:
    return {
        "address": address,
        "price": price,
        "sqft": sqft,
        "beds": beds,
        "baths": baths,
        "distance_miles": distance_miles,
        "sold_date": days_ago(sold_days_ago),
        "source": source,
        "listing_type": listing_type,
        "description": description,
    }


def make_subject(sqft: int = 1200, beds: int = 3, baths: float = 1.0) -> dict:
    return {"sqft": sqft, "beds": beds, "baths": baths}


# ── is_distressed ────────────────────────────────────────────────────────────

class TestIsDistressed:
    def test_clean_listing_not_distressed(self):
        comp = make_comp(listing_type="Single Family", description="Nice home")
        assert is_distressed(comp) is False

    def test_foreclosure_in_listing_type(self):
        comp = make_comp(listing_type="Foreclosure")
        assert is_distressed(comp) is True

    def test_reo_in_description(self):
        comp = make_comp(description="Bank owned REO property")
        assert is_distressed(comp) is True

    def test_short_sale_keyword(self):
        comp = make_comp(description="Short sale subject to bank approval")
        assert is_distressed(comp) is True

    def test_auction_keyword(self):
        comp = make_comp(listing_type="Auction")
        assert is_distressed(comp) is True

    def test_case_insensitive(self):
        comp = make_comp(description="BANK OWNED property")
        assert is_distressed(comp) is True

    def test_estate_sale_not_distressed(self):
        """'Estate sale' is normal — a family estate, not a distressed bank sale."""
        comp = make_comp(description="Estate sale, moving quickly")
        assert is_distressed(comp) is False


# ── score_comp ───────────────────────────────────────────────────────────────

class TestScoreComp:
    def test_perfect_comp_scores_100(self):
        """Identical comp nearby and recent should score 100."""
        comp = make_comp(distance_miles=0.0, sold_days_ago=0, sqft=1200, beds=3, baths=1.0)
        subject = make_subject(sqft=1200, beds=3, baths=1.0)
        score = score_comp(comp, subject)
        assert score == pytest.approx(100.0, abs=1.0)

    def test_distance_penalty(self):
        """Comp 1 mile away should score less than comp 0.1 miles away."""
        comp_close = make_comp(distance_miles=0.1)
        comp_far = make_comp(distance_miles=1.0)
        subject = make_subject()
        assert score_comp(comp_close, subject) > score_comp(comp_far, subject)

    def test_recency_penalty(self):
        """Older sold date should score lower."""
        comp_recent = make_comp(sold_days_ago=30)
        comp_old = make_comp(sold_days_ago=500)
        subject = make_subject()
        assert score_comp(comp_recent, subject) > score_comp(comp_old, subject)

    def test_sqft_penalty(self):
        """Larger sqft difference reduces score."""
        comp_match = make_comp(sqft=1200)
        comp_differ = make_comp(sqft=2000)
        subject = make_subject(sqft=1200)
        assert score_comp(comp_match, subject) > score_comp(comp_differ, subject)

    def test_beds_penalty(self):
        """Bedroom mismatch reduces score."""
        comp_match = make_comp(beds=3)
        comp_differ = make_comp(beds=5)
        subject = make_subject(beds=3)
        assert score_comp(comp_match, subject) > score_comp(comp_differ, subject)

    def test_baths_penalty(self):
        """Bathroom mismatch reduces score."""
        comp_match = make_comp(baths=1.0)
        comp_differ = make_comp(baths=3.0)
        subject = make_subject(baths=1.0)
        assert score_comp(comp_match, subject) > score_comp(comp_differ, subject)

    def test_score_non_negative(self):
        """Score is always >= 0 even for terrible comps."""
        comp = make_comp(distance_miles=5.0, sold_days_ago=1000, sqft=5000, beds=6, baths=4.0)
        subject = make_subject(sqft=1000, beds=2, baths=1.0)
        assert score_comp(comp, subject) >= 0.0

    def test_score_max_100(self):
        """Score is always <= 100."""
        comp = make_comp(distance_miles=0.0, sold_days_ago=0)
        subject = make_subject()
        assert score_comp(comp, subject) <= 100.0

    def test_missing_sqft_gives_partial_credit(self):
        """If comp has no sqft, it should still get partial credit."""
        comp = make_comp()
        comp["sqft"] = None
        subject = make_subject(sqft=1200)
        score_no_sqft = score_comp(comp, subject)
        comp["sqft"] = 1200
        score_with_sqft = score_comp(comp, subject)
        assert score_no_sqft < score_with_sqft
        assert score_no_sqft > 0

    def test_weights_sum_to_100(self):
        """Distance(30)+recency(25)+sqft(20)+beds(15)+baths(10) = 100."""
        assert 30 + 25 + 20 + 15 + 10 == 100


# ── filter_comps_tiered ──────────────────────────────────────────────────────

class TestFilterCompsTiered:
    def _good_comps(self, n: int = 5) -> list[dict]:
        return [
            make_comp(
                address=f"{i} Main St",
                distance_miles=0.2,
                sold_days_ago=90,
                sqft=1200,
                beds=3,
                baths=1.0,
            )
            for i in range(n)
        ]

    def test_tight_tier_when_enough_comps(self):
        """With 5 good comps nearby, should use tier 1."""
        comps = self._good_comps(5)
        subject = make_subject()
        filtered, tier = filter_comps_tiered(comps, subject)
        assert tier == 1
        assert len(filtered) >= 3

    def test_widens_to_tier2_when_too_few(self):
        """One comp within 0.5mi → should widen to tier 2."""
        comps = [
            make_comp(distance_miles=0.3, sold_days_ago=60),   # passes tier 1
            make_comp(distance_miles=0.8, sold_days_ago=60),   # passes tier 2
            make_comp(distance_miles=0.9, sold_days_ago=60),   # passes tier 2
        ]
        subject = make_subject()
        filtered, tier = filter_comps_tiered(comps, subject)
        assert tier == 2
        assert len(filtered) == 3

    def test_widens_to_tier3_when_still_too_few(self):
        """All comps far away → should reach tier 3."""
        comps = [
            make_comp(distance_miles=1.5, sold_days_ago=60),
            make_comp(distance_miles=1.6, sold_days_ago=60),
            make_comp(distance_miles=1.7, sold_days_ago=60),
        ]
        subject = make_subject()
        filtered, tier = filter_comps_tiered(comps, subject)
        assert tier == 3
        assert len(filtered) == 3

    def test_excludes_distressed(self):
        """Distressed comps are excluded from all tiers."""
        comps = [
            make_comp(address="1 Main", distance_miles=0.1, description="Bank owned REO"),
            make_comp(address="2 Main", distance_miles=0.1),
            make_comp(address="3 Main", distance_miles=0.1),
            make_comp(address="4 Main", distance_miles=0.1),
        ]
        subject = make_subject()
        filtered, _ = filter_comps_tiered(comps, subject)
        assert all(c["address"] != "1 Main" for c in filtered)

    def test_returns_empty_when_no_comps(self):
        filtered, tier = filter_comps_tiered([], make_subject())
        assert filtered == []
        assert tier == 3

    def test_excludes_old_comps_in_tier1(self):
        """Tier 1 max age is 6 months (~180 days)."""
        comps = [
            make_comp(address="recent", sold_days_ago=90, distance_miles=0.2),
            make_comp(address="old", sold_days_ago=400, distance_miles=0.2),
        ]
        subject = make_subject()
        _, tier = filter_comps_tiered(comps, subject)
        # Not enough for tier 1 (only 1 recent), should widen
        assert tier > 1


# ── estimate_arv ─────────────────────────────────────────────────────────────

class TestEstimateARV:
    def _comps(self, prices: list[float]) -> list[dict]:
        return [
            make_comp(price=p, address=f"{i} St", distance_miles=0.2)
            for i, p in enumerate(prices)
        ]

    def test_basic_arv_estimate(self):
        comps = self._comps([80_000, 85_000, 90_000, 95_000, 100_000])
        result = estimate_arv(comps, make_subject())
        assert isinstance(result, ARVEstimate)
        assert 80_000 <= result.arv <= 100_000

    def test_arv_conservative_lower_than_arv(self):
        comps = self._comps([80_000, 85_000, 90_000, 95_000, 100_000])
        result = estimate_arv(comps, make_subject())
        assert result.arv_conservative <= result.arv

    def test_arv_aggressive_higher_than_arv(self):
        comps = self._comps([80_000, 85_000, 90_000, 95_000, 100_000])
        result = estimate_arv(comps, make_subject())
        assert result.arv_aggressive >= result.arv

    def test_comp_count_reflects_used(self):
        comps = self._comps([80_000, 85_000, 90_000])
        result = estimate_arv(comps, make_subject())
        assert result.comp_count == 3

    def test_distressed_excluded_from_arv(self):
        comps = [
            make_comp(price=40_000, description="Bank owned REO", distance_miles=0.2),
            make_comp(price=85_000, distance_miles=0.2),
            make_comp(price=90_000, distance_miles=0.2),
            make_comp(price=95_000, distance_miles=0.2),
        ]
        result = estimate_arv(comps, make_subject())
        # ARV should not be dragged down by the $40k distressed sale
        assert result.arv > 60_000

    def test_empty_comps_returns_none_arv(self):
        result = estimate_arv([], make_subject())
        assert result.arv is None
        assert result.comp_count == 0

    def test_arv_weighted_by_score(self):
        """Higher-scored comps (close, recent) should have more weight."""
        comps = [
            make_comp(price=100_000, distance_miles=0.1, sold_days_ago=30),  # excellent
            make_comp(price=50_000, distance_miles=1.9, sold_days_ago=700),  # terrible
        ]
        result = estimate_arv(comps, make_subject())
        # The excellent comp should pull ARV closer to 100k
        assert result.arv > 75_000

    def test_filter_tier_recorded(self):
        comps = [make_comp(distance_miles=0.2) for _ in range(5)]
        result = estimate_arv(comps, make_subject())
        assert result.filter_tier in (1, 2, 3)
