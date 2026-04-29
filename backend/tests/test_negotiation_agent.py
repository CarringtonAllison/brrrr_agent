"""Tests for negotiation_agent (Haiku) — offer range with code-clamped ceiling."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.negotiation_agent import NegotiationAdvice, suggest_offer


def make_listing(**overrides) -> dict:
    # ARV=160k, sqft=1100 → medium rehab ~$44k → max breakeven ~$68k
    base = {
        "id": "listing-1",
        "address": "123 Elm St",
        "price": 75_000,
        "arv": 160_000,
        "estimated_rent": 1400,
        "beds": 3,
        "baths": 1.5,
        "sqft": 1100,
        "description": "Motivated seller, must sell",
        "days_on_market": 90,
        "motivation_score": 7,
        "brrrr": {"grade": "GOOD", "cash_left_in_deal": 12_000},
    }
    base.update(overrides)
    return base


def _final_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    resp.content = [block]
    return resp


# ── Successful suggestion ─────────────────────────────────────────────────────

class TestSuggestOffer:
    def test_returns_negotiation_advice(self):
        # ARV=160k, rehab≈44k → max breakeven ≈ $68k
        payload = {
            "offer_range_low": 55_000,
            "offer_range_high": 65_000,
            "rationale": "High DOM and motivation signals — can push hard.",
            "tactics": ["lead with cash close", "ask for 5k credit"],
        }
        with patch("backend.agents.negotiation_agent.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _final_response(payload)
            mock_class.return_value = mock_client
            advice = suggest_offer(make_listing(), api_key="test-key")
        assert isinstance(advice, NegotiationAdvice)
        assert advice.offer_range_low == 55_000
        assert "cash close" in " ".join(advice.tactics).lower()

    def test_offer_high_clamped_to_max_breakeven(self):
        """If Claude suggests an offer above max_purchase_breakeven, clamp it."""
        # ARV=160k → breakeven ≈ $68k. 95k is above ceiling.
        payload = {
            "offer_range_low": 80_000,
            "offer_range_high": 95_000,
            "rationale": "Crazy aggressive",
            "tactics": [],
        }
        with patch("backend.agents.negotiation_agent.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _final_response(payload)
            mock_class.return_value = mock_client
            advice = suggest_offer(make_listing(), api_key="test-key")

        # Both must be at or below breakeven (~46.6k for these inputs)
        assert advice.offer_range_high <= advice.max_purchase_breakeven
        assert advice.was_clamped is True

    def test_offer_not_clamped_when_within_breakeven(self):
        payload = {
            "offer_range_low": 50_000,
            "offer_range_high": 60_000,
            "rationale": "Conservative",
            "tactics": [],
        }
        with patch("backend.agents.negotiation_agent.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _final_response(payload)
            mock_class.return_value = mock_client
            advice = suggest_offer(make_listing(), api_key="test-key")
        assert advice.was_clamped is False
        assert advice.offer_range_high == 60_000

    def test_low_does_not_exceed_high_after_clamp(self):
        """If low > clamped high, low must also be clamped."""
        # Both above ~$68k breakeven
        payload = {
            "offer_range_low": 90_000,
            "offer_range_high": 100_000,
            "rationale": "Both too high",
            "tactics": [],
        }
        with patch("backend.agents.negotiation_agent.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _final_response(payload)
            mock_class.return_value = mock_client
            advice = suggest_offer(make_listing(), api_key="test-key")
        assert advice.offer_range_low <= advice.offer_range_high


# ── Fallbacks ─────────────────────────────────────────────────────────────────

class TestFallbacks:
    def test_no_api_key_returns_calculation_only(self):
        """Without an API key, return a deterministic offer based on max breakeven."""
        advice = suggest_offer(make_listing(), api_key="")
        assert advice.offer_range_high <= advice.max_purchase_breakeven
        assert "AI unavailable" in advice.rationale or advice.was_clamped is False

    def test_invalid_json_falls_back(self):
        resp = MagicMock()
        resp.stop_reason = "end_turn"
        block = MagicMock()
        block.type = "text"
        block.text = "not json"
        resp.content = [block]

        with patch("backend.agents.negotiation_agent.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = resp
            mock_class.return_value = mock_client
            advice = suggest_offer(make_listing(), api_key="test-key")
        assert advice.offer_range_high <= advice.max_purchase_breakeven

    def test_api_error_falls_back(self):
        with patch("backend.agents.negotiation_agent.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = Exception("boom")
            mock_class.return_value = mock_client
            advice = suggest_offer(make_listing(), api_key="test-key")
        assert advice.offer_range_high <= advice.max_purchase_breakeven
