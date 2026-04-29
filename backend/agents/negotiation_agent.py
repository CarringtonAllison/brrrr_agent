"""Negotiation agent (Haiku) — offer range with code-clamped ceiling.

Critical invariant: offer_range_high CAN NEVER exceed max_purchase_breakeven.
Whatever the model says, we clamp in code.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic

from backend.agents.tools import (
    TOOL_DEFINITIONS_NEGOTIATION,
    estimate_rehab_costs,
    run_tool,
)
from backend.brrrr_calculator import compute_max_purchase_price
from backend.config import HAIKU_MODEL

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a negotiation coach for a BRRRR investor.

Goal: produce an offer range (low/high) and tactics that get a deal done at the right price.

Operating principles:
- Use analyze_seller_motivation to gauge how hard you can push.
- Use calculate_max_purchase_price to find the ceiling — never recommend above it.
- Higher motivation → wider gap below asking. Lower motivation → tighter, closer to ask.
- Be tactical. Cash close, no contingencies, quick close, credits — name the lever, not the cliché.

Output a single JSON object — no markdown fences, no commentary outside JSON:
{
  "offer_range_low": number,
  "offer_range_high": number,
  "rationale": "one or two sentence explanation",
  "tactics": ["tactic 1", "tactic 2"]
}
"""


@dataclass
class NegotiationAdvice:
    offer_range_low: float
    offer_range_high: float
    rationale: str
    tactics: list[str] = field(default_factory=list)
    max_purchase_breakeven: float = 0.0
    was_clamped: bool = False


def _listing_context(listing: dict) -> str:
    keep = [
        "address", "price", "arv", "estimated_rent", "beds", "baths", "sqft",
        "days_on_market", "description", "motivation_score", "motivation_signals", "brrrr",
    ]
    snapshot = {k: listing.get(k) for k in keep if listing.get(k) is not None}
    return json.dumps(snapshot, default=str, indent=2)


def _extract_text(content_blocks: list[Any]) -> str:
    return "".join(b.text for b in content_blocks if getattr(b, "type", None) == "text")


def _parse_advice(text: str) -> tuple[float, float, str, list[str]] | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
        return (
            float(data["offer_range_low"]),
            float(data["offer_range_high"]),
            str(data.get("rationale", "")),
            list(data.get("tactics", [])),
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def _compute_breakeven(listing: dict) -> float:
    """Compute the absolute ceiling for any offer."""
    arv = listing.get("arv") or 0
    sqft = listing.get("sqft") or 1000
    rehab = estimate_rehab_costs(sqft=sqft, condition="medium")["rehab_estimate"]
    return compute_max_purchase_price(arv=arv, rehab_cost=rehab, max_cash_left=0)


def _clamp(low: float, high: float, ceiling: float) -> tuple[float, float, bool]:
    """Clamp offer range to ceiling. Returns (low, high, was_clamped)."""
    clamped = False
    if high > ceiling:
        high = ceiling
        clamped = True
    if low > high:
        low = high
        clamped = True
    return low, high, clamped


def _fallback_advice(listing: dict, reason: str) -> NegotiationAdvice:
    """Produce a deterministic offer when the model is unavailable."""
    breakeven = _compute_breakeven(listing)
    # Conservative default range: 80–95% of breakeven
    high = breakeven * 0.95
    low = breakeven * 0.80
    return NegotiationAdvice(
        offer_range_low=round(low, 2),
        offer_range_high=round(high, 2),
        rationale=f"AI unavailable ({reason}); offering deterministic 80–95% of max breakeven.",
        tactics=["cash close", "as-is purchase", "10-day inspection cap"],
        max_purchase_breakeven=round(breakeven, 2),
        was_clamped=False,
    )


def suggest_offer(
    listing: dict,
    api_key: str | None = None,
    max_iterations: int = 4,
) -> NegotiationAdvice:
    """Suggest an offer range using Haiku, clamped to max breakeven."""
    breakeven = _compute_breakeven(listing)

    if not api_key:
        return _fallback_advice(listing, "no API key")

    try:
        client = Anthropic(api_key=api_key)
    except Exception as exc:
        return _fallback_advice(listing, f"client init failed: {exc}")

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                f"Listing:\n{_listing_context(listing)}\n\n"
                f"Computed max breakeven (do not exceed): ${breakeven:,.0f}\n\n"
                "Produce the offer-range JSON per the system prompt schema."
            ),
        }
    ]

    parsed: tuple[float, float, str, list[str]] | None = None

    for _ in range(max_iterations):
        try:
            resp = client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS_NEGOTIATION,
                messages=messages,
            )
        except Exception as exc:
            logger.warning(f"negotiation_agent API error: {exc}")
            return _fallback_advice(listing, f"API error: {exc}")

        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for block in resp.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                output = run_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })
            messages.append({"role": "user", "content": tool_results})
            continue

        text = _extract_text(resp.content)
        parsed = _parse_advice(text)
        break

    if parsed is None:
        return _fallback_advice(listing, "unparseable model output")

    low, high, rationale, tactics = parsed
    low, high, was_clamped = _clamp(low, high, breakeven)
    return NegotiationAdvice(
        offer_range_low=round(low, 2),
        offer_range_high=round(high, 2),
        rationale=rationale,
        tactics=tactics,
        max_purchase_breakeven=round(breakeven, 2),
        was_clamped=was_clamped,
    )
