"""Tests for deal_analyst (Sonnet) — tool-use loop, JSON parsing, fallback."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.deal_analyst import DealReview, review_deal, ask_about_deal


def make_listing(**overrides) -> dict:
    base = {
        "id": "listing-1",
        "address": "123 Elm St",
        "city": "Cleveland",
        "state": "OH",
        "zip_code": "44101",
        "price": 65_000,
        "arv": 95_000,
        "estimated_rent": 950,
        "beds": 3,
        "baths": 1.5,
        "sqft": 1100,
        "description": "Needs paint and carpet, motivated seller",
        "days_on_market": 60,
        "latitude": 41.5,
        "longitude": -81.7,
        "brrrr": {"grade": "GOOD", "cash_left_in_deal": 8000, "monthly_cashflow": 200},
    }
    base.update(overrides)
    return base


def _msg_block(text: str) -> dict:
    return {"type": "text", "text": text}


def _final_response(payload: dict) -> MagicMock:
    """Mock a final Anthropic response that emits JSON in a text block."""
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    resp.content = [block]
    return resp


def _tool_use_response(tool_name: str, tool_input: dict, tool_use_id: str = "tu-1") -> MagicMock:
    """Mock a response where Claude requests a tool call."""
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_use_id
    block.name = tool_name
    block.input = tool_input
    resp.content = [block]
    return resp


# ── review_deal: structured JSON review ───────────────────────────────────────

class TestReviewDeal:
    def test_returns_review_dataclass(self):
        payload = {
            "verdict": "GOOD",
            "summary": "Solid BRRRR — comps support ARV and rent is achievable.",
            "risks": ["older roof"],
            "opportunities": ["likely under-priced"],
            "confidence": 0.75,
        }
        with patch("backend.agents.deal_analyst.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _final_response(payload)
            mock_class.return_value = mock_client
            review = review_deal(make_listing(), api_key="test-key")
        assert isinstance(review, DealReview)
        assert review.verdict == "GOOD"
        assert review.confidence == 0.75
        assert "older roof" in review.risks

    def test_handles_tool_use_loop(self):
        """Claude requests a tool, we run it, then Claude responds with final JSON."""
        tool_resp = _tool_use_response(
            "calculate_brrrr_scenarios",
            {"purchase_price": 65000, "arv": 95000, "estimated_rent": 950},
        )
        final_resp = _final_response({
            "verdict": "STRONG", "summary": "Stress-tested OK", "risks": [],
            "opportunities": [], "confidence": 0.85,
        })

        with patch("backend.agents.deal_analyst.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = [tool_resp, final_resp]
            mock_class.return_value = mock_client
            review = review_deal(make_listing(), api_key="test-key")

        assert review.verdict == "STRONG"
        assert mock_client.messages.create.call_count == 2

    def test_fallback_on_invalid_json(self):
        """If Claude returns non-JSON text, fall back gracefully."""
        resp = MagicMock()
        resp.stop_reason = "end_turn"
        block = MagicMock()
        block.type = "text"
        block.text = "I cannot evaluate this deal at this time."
        resp.content = [block]

        with patch("backend.agents.deal_analyst.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = resp
            mock_class.return_value = mock_client
            review = review_deal(make_listing(), api_key="test-key")

        assert review.verdict == "UNKNOWN"
        assert review.confidence == 0.0
        assert review.summary  # not empty

    def test_fallback_on_api_error(self):
        with patch("backend.agents.deal_analyst.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = Exception("API down")
            mock_class.return_value = mock_client
            review = review_deal(make_listing(), api_key="test-key")
        assert review.verdict == "UNKNOWN"
        assert "error" in review.summary.lower() or review.confidence == 0.0

    def test_no_api_key_returns_skip(self):
        review = review_deal(make_listing(), api_key="")
        assert review.verdict == "UNKNOWN"
        assert review.confidence == 0.0

    def test_max_iterations_breaks_runaway_loop(self):
        """If Claude keeps requesting tools forever, cap iterations and fall back."""
        tool_resp = _tool_use_response("estimate_rehab_costs", {"sqft": 1000})
        with patch("backend.agents.deal_analyst.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = tool_resp
            mock_class.return_value = mock_client
            review = review_deal(make_listing(), api_key="test-key", max_iterations=3)
        # Should have hit the cap and not raised
        assert mock_client.messages.create.call_count == 3
        assert review.verdict == "UNKNOWN"


# ── ask_about_deal: free-form Q&A ─────────────────────────────────────────────

class TestAskAboutDeal:
    def test_simple_text_response(self):
        resp = MagicMock()
        resp.stop_reason = "end_turn"
        block = MagicMock()
        block.type = "text"
        block.text = "The biggest risk here is the older roof — budget $8k extra."
        resp.content = [block]

        with patch("backend.agents.deal_analyst.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = resp
            mock_class.return_value = mock_client
            answer = ask_about_deal(
                make_listing(),
                question="What's the biggest risk?",
                api_key="test-key",
            )
        assert "older roof" in answer

    def test_no_api_key_returns_message(self):
        answer = ask_about_deal(make_listing(), question="anything", api_key="")
        assert "not configured" in answer.lower() or "unavailable" in answer.lower()

    def test_api_error_returns_message(self):
        with patch("backend.agents.deal_analyst.Anthropic") as mock_class:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = Exception("rate limited")
            mock_class.return_value = mock_client
            answer = ask_about_deal(make_listing(), question="anything", api_key="test-key")
        assert "error" in answer.lower() or "unavailable" in answer.lower()
