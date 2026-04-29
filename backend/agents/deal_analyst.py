"""Deal analyst (Sonnet) — structured BRRRR review with tool-use loop.

System prompt encodes our skeptical investing posture:
- "Never accept numbers at face value."
- "Always run at least one downside scenario."
- "If comp data is thin, say so."
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic

from backend.agents.tools import TOOL_DEFINITIONS_DEAL_ANALYST, run_tool
from backend.config import SONNET_MODEL

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a skeptical real-estate analyst reviewing BRRRR deals for an investor.

Operating principles:
- Never accept numbers at face value. Always validate ARV with comp logic and rent against HUD FMR.
- Always run at least one downside scenario (calculate_brrrr_scenarios) before assigning a verdict.
- If comp data is thin or rent is unverified, lower confidence and say so.
- Use tools when they sharpen the answer — do not call tools you do not need.
- Be terse. Investors want signal, not narrative.

Output the final review as a single JSON object with this exact shape:
{
  "verdict": "STRONG" | "GOOD" | "MAYBE" | "SKIP",
  "summary": "two-to-three sentence plain-English assessment",
  "risks": ["risk 1", "risk 2"],
  "opportunities": ["opportunity 1"],
  "confidence": 0.0-1.0
}

Do not wrap the JSON in markdown fences. Do not add commentary outside the JSON.
"""


ASK_SYSTEM_PROMPT = """You are a real-estate investing advisor answering questions about a specific BRRRR deal.

Be direct, specific, and grounded in the listing data provided.
Use tools when a question requires fresh lookups (FMR, taxes, flood zone, demographics).
Keep answers concise — investors want signal, not narrative.
"""


@dataclass
class DealReview:
    verdict: str
    summary: str
    risks: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    confidence: float = 0.0
    raw_text: str = ""


def _listing_context(listing: dict) -> str:
    """Render a listing dict as a compact prompt block."""
    keep = [
        "address", "city", "state", "zip_code", "price", "arv", "estimated_rent",
        "beds", "baths", "sqft", "year_built", "days_on_market", "description",
        "latitude", "longitude", "brrrr", "motivation_score", "motivation_signals",
    ]
    snapshot = {k: listing.get(k) for k in keep if listing.get(k) is not None}
    return json.dumps(snapshot, default=str, indent=2)


def _extract_text(content_blocks: list[Any]) -> str:
    """Concatenate text blocks from a Claude response."""
    return "".join(b.text for b in content_blocks if getattr(b, "type", None) == "text")


def _parse_review_json(text: str) -> DealReview | None:
    """Extract a DealReview from Claude's JSON output. Returns None on failure."""
    text = text.strip()
    if text.startswith("```"):
        # Strip optional markdown fence
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    verdict = data.get("verdict", "").upper()
    if verdict not in {"STRONG", "GOOD", "MAYBE", "SKIP"}:
        return None
    return DealReview(
        verdict=verdict,
        summary=str(data.get("summary", "")),
        risks=list(data.get("risks", [])),
        opportunities=list(data.get("opportunities", [])),
        confidence=float(data.get("confidence", 0.0)),
        raw_text=text,
    )


def _fallback_review(reason: str) -> DealReview:
    return DealReview(
        verdict="UNKNOWN",
        summary=f"AI review unavailable: {reason}",
        risks=[],
        opportunities=[],
        confidence=0.0,
    )


def review_deal(
    listing: dict,
    api_key: str | None = None,
    max_iterations: int = 6,
) -> DealReview:
    """Run a deal review through Sonnet with tool-use enabled.

    Returns a DealReview. On any error or unparseable output, returns a fallback
    review with verdict=UNKNOWN and confidence=0.
    """
    if not api_key:
        return _fallback_review("ANTHROPIC_API_KEY not configured")

    try:
        client = Anthropic(api_key=api_key)
    except Exception as exc:
        return _fallback_review(f"client init failed: {exc}")

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                "Review this BRRRR deal. Use tools as needed, then return the final "
                "review as a single JSON object per the system prompt schema.\n\n"
                f"Listing:\n{_listing_context(listing)}"
            ),
        }
    ]

    for _ in range(max_iterations):
        try:
            resp = client.messages.create(
                model=SONNET_MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS_DEAL_ANALYST,
                messages=messages,
            )
        except Exception as exc:
            logger.warning(f"deal_analyst API error: {exc}")
            return _fallback_review(f"API error: {exc}")

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

        # end_turn (or anything else) — try to parse final JSON
        text = _extract_text(resp.content)
        review = _parse_review_json(text)
        if review is None:
            return _fallback_review("unparseable JSON output")
        return review

    return _fallback_review("max iterations reached")


def ask_about_deal(
    listing: dict,
    question: str,
    api_key: str | None = None,
    max_iterations: int = 6,
) -> str:
    """Answer a free-form question about a specific deal. Returns plain text."""
    if not api_key:
        return "AI is not configured. Set ANTHROPIC_API_KEY to enable Q&A."

    try:
        client = Anthropic(api_key=api_key)
    except Exception as exc:
        return f"AI unavailable: {exc}"

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                f"Listing context:\n{_listing_context(listing)}\n\n"
                f"Question: {question}"
            ),
        }
    ]

    for _ in range(max_iterations):
        try:
            resp = client.messages.create(
                model=SONNET_MODEL,
                max_tokens=1024,
                system=ASK_SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS_DEAL_ANALYST,
                messages=messages,
            )
        except Exception as exc:
            logger.warning(f"ask_about_deal API error: {exc}")
            return f"AI unavailable due to error: {exc}"

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

        return _extract_text(resp.content).strip() or "(no answer)"

    return "AI unavailable: max iterations reached without final answer."
