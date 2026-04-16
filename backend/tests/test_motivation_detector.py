"""Tests for motivation detector — keyword matching and seller motivation scoring."""

from __future__ import annotations

import pytest

from backend.motivation_detector import (
    detect_high_signals,
    detect_medium_signals,
    detect_low_signals,
    detect_condition_patterns,
    score_motivation,
    MotivationResult,
)


def make_listing(description: str = "", title: str = "", dom: int = 30) -> dict:
    return {
        "description": description,
        "title": title,
        "days_on_market": dom,
    }


# ── detect_high_signals ───────────────────────────────────────────────────────

class TestDetectHighSignals:
    def test_motivated_seller(self):
        listing = make_listing(description="Motivated seller, must sell fast")
        assert len(detect_high_signals(listing)) > 0

    def test_price_reduced(self):
        listing = make_listing(description="Price reduced, bring all offers")
        assert len(detect_high_signals(listing)) > 0

    def test_must_sell(self):
        listing = make_listing(description="Must sell this week")
        assert len(detect_high_signals(listing)) > 0

    def test_relocating(self):
        listing = make_listing(description="Relocating out of state")
        assert len(detect_high_signals(listing)) > 0

    def test_divorce(self):
        listing = make_listing(description="Divorce sale, priced to move")
        assert len(detect_high_signals(listing)) > 0

    def test_clean_listing_no_signals(self):
        listing = make_listing(description="Beautiful updated kitchen, new roof")
        assert detect_high_signals(listing) == []

    def test_case_insensitive(self):
        listing = make_listing(description="MOTIVATED SELLER, MUST SELL")
        assert len(detect_high_signals(listing)) > 0


# ── detect_medium_signals ────────────────────────────────────────────────────

class TestDetectMediumSignals:
    def test_priced_to_sell(self):
        listing = make_listing(description="Priced to sell quickly")
        assert len(detect_medium_signals(listing)) > 0

    def test_as_is(self):
        listing = make_listing(description="Sold as-is, cash buyers preferred")
        assert len(detect_medium_signals(listing)) > 0

    def test_bring_all_offers(self):
        listing = make_listing(description="Bring all offers!")
        assert len(detect_medium_signals(listing)) > 0

    def test_estate(self):
        listing = make_listing(description="Estate sale, settling quickly")
        assert len(detect_medium_signals(listing)) > 0

    def test_fixer_upper(self):
        listing = make_listing(description="Great fixer-upper opportunity")
        assert len(detect_medium_signals(listing)) > 0

    def test_clean_listing_no_medium(self):
        listing = make_listing(description="Move-in ready, fully updated")
        assert detect_medium_signals(listing) == []


# ── detect_low_signals ───────────────────────────────────────────────────────

class TestDetectLowSignals:
    def test_cash_preferred(self):
        listing = make_listing(description="Cash buyers preferred")
        assert len(detect_low_signals(listing)) > 0

    def test_handyman_special(self):
        listing = make_listing(description="Handyman special, great bones")
        assert len(detect_low_signals(listing)) > 0

    def test_tlc(self):
        listing = make_listing(description="Needs TLC but great location")
        assert len(detect_low_signals(listing)) > 0

    def test_investor_special(self):
        listing = make_listing(description="Investor special, high cap rate")
        assert len(detect_low_signals(listing)) > 0

    def test_high_dom_is_low_signal(self):
        """Listings on market 90+ days get a low motivation signal."""
        listing = make_listing(dom=95)
        assert len(detect_low_signals(listing)) > 0

    def test_low_dom_no_signal(self):
        listing = make_listing(dom=10)
        assert detect_low_signals(listing) == []


# ── detect_condition_patterns ────────────────────────────────────────────────

class TestDetectConditionPatterns:
    def test_needs_roof(self):
        listing = make_listing(description="Needs new roof")
        result = detect_condition_patterns(listing)
        assert any("roof" in s.lower() for s in result)

    def test_foundation_issue(self):
        listing = make_listing(description="Some foundation issues noted")
        result = detect_condition_patterns(listing)
        assert any("foundation" in s.lower() for s in result)

    def test_water_damage(self):
        listing = make_listing(description="Signs of water damage in basement")
        result = detect_condition_patterns(listing)
        assert any("water" in s.lower() for s in result)

    def test_clean_no_conditions(self):
        listing = make_listing(description="Move-in ready, newly renovated")
        assert detect_condition_patterns(listing) == []


# ── score_motivation (full pipeline) ─────────────────────────────────────────

class TestScoreMotivation:
    def test_returns_motivation_result(self):
        result = score_motivation(make_listing())
        assert isinstance(result, MotivationResult)

    def test_score_range_1_to_10(self):
        listing = make_listing(description="Motivated seller must sell today divorce")
        result = score_motivation(listing)
        assert 1 <= result.score <= 10

    def test_neutral_listing_scores_mid_low(self):
        listing = make_listing(description="Nice home, great neighborhood")
        result = score_motivation(listing)
        assert result.score <= 5

    def test_high_signal_listing_scores_high(self):
        listing = make_listing(
            description="MOTIVATED SELLER! Must sell, relocating, price reduced, divorce"
        )
        result = score_motivation(listing)
        assert result.score >= 7

    def test_signals_list_populated(self):
        listing = make_listing(description="Motivated seller, as-is, cash preferred")
        result = score_motivation(listing)
        assert len(result.signals) > 0

    def test_no_signals_empty_list(self):
        listing = make_listing(description="Beautiful updated home")
        result = score_motivation(listing)
        assert result.signals == []

    def test_high_dom_increases_score(self):
        low_dom = score_motivation(make_listing(description="Handyman special", dom=10))
        high_dom = score_motivation(make_listing(description="Handyman special", dom=180))
        assert high_dom.score >= low_dom.score

    def test_multiple_high_signals_max_score(self):
        listing = make_listing(
            description="Motivated seller, must sell, relocating, divorce, price reduced, bring offers"
        )
        result = score_motivation(listing)
        assert result.score == 10
