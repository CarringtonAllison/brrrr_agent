"""Motivation detector — keyword-based seller motivation scoring.

Scores listings 1-10 based on tiered keyword signals and condition patterns.
Higher scores indicate more motivated sellers → better negotiation leverage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── Signal keyword tiers ──────────────────────────────────────────────────────

_HIGH_PATTERNS = re.compile(
    r"\b(motivated seller|must sell|price[d]? reduced|price drop|"
    r"reloc[a-z]+|divorce|liquidat[a-z]+|bank[- ]?owned|foreclos[a-z]+|"
    r"short[- ]?sale|reo|auction|back on market|price improvement)\b",
    re.IGNORECASE,
)

_MEDIUM_PATTERNS = re.compile(
    r"\b(priced to sell|as[- ]is|bring (all )?offers?|"
    r"estate sale|fixer[- ]?upper|make an offer|motivated|quick close|"
    r"cash only|needs work|below market)\b",
    re.IGNORECASE,
)

_LOW_PATTERNS = re.compile(
    r"\b(cash (buyers? )?(preferred|welcome)|handyman special|"
    r"investor special|needs tlc|tlc|great bones|"
    r"sweat equity|diamond in the rough|potential)\b",
    re.IGNORECASE,
)

_CONDITION_PATTERNS = [
    (re.compile(r"\b(needs? (new )?roof|roof[- ]?issue|roofing)\b", re.IGNORECASE), "roof issue"),
    (re.compile(r"\bfoundation\b", re.IGNORECASE), "foundation issue"),
    (re.compile(r"\bwater damage\b", re.IGNORECASE), "water damage"),
    (re.compile(r"\bmold\b", re.IGNORECASE), "mold"),
    (re.compile(r"\bflooding?\b", re.IGNORECASE), "flooding"),
    (re.compile(r"\bfire damage\b", re.IGNORECASE), "fire damage"),
    (re.compile(r"\bstructural\b", re.IGNORECASE), "structural issue"),
]

HIGH_DOM_THRESHOLD = 90  # days on market → low motivation signal


def _listing_text(listing: dict) -> str:
    return " ".join([
        listing.get("description", "") or "",
        listing.get("title", "") or "",
    ])


def detect_high_signals(listing: dict) -> list[str]:
    """Return matched high-tier motivation keywords."""
    text = _listing_text(listing)
    return list({m.group(0).lower() for m in _HIGH_PATTERNS.finditer(text)})


def detect_medium_signals(listing: dict) -> list[str]:
    """Return matched medium-tier motivation keywords."""
    text = _listing_text(listing)
    return list({m.group(0).lower() for m in _MEDIUM_PATTERNS.finditer(text)})


def detect_low_signals(listing: dict) -> list[str]:
    """Return matched low-tier motivation keywords plus high DOM signal."""
    text = _listing_text(listing)
    signals = list({m.group(0).lower() for m in _LOW_PATTERNS.finditer(text)})

    dom = listing.get("days_on_market") or 0
    if dom >= HIGH_DOM_THRESHOLD:
        signals.append(f"{dom} days on market")

    return signals


def detect_condition_patterns(listing: dict) -> list[str]:
    """Return matched condition issue labels (roof, foundation, etc.)."""
    text = _listing_text(listing)
    found = []
    for pattern, label in _CONDITION_PATTERNS:
        if pattern.search(text):
            found.append(label)
    return found


# ── Scoring ───────────────────────────────────────────────────────────────────

# Points per signal tier
HIGH_PTS = 3
MEDIUM_PTS = 2
LOW_PTS = 1
CONDITION_PTS = 1
BASE_SCORE = 1


@dataclass
class MotivationResult:
    score: int          # 1-10
    signals: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)


def score_motivation(listing: dict) -> MotivationResult:
    """Score seller motivation 1-10.

    1 = no signals, 10 = maximum motivation.
    """
    high = detect_high_signals(listing)
    medium = detect_medium_signals(listing)
    low = detect_low_signals(listing)
    conditions = detect_condition_patterns(listing)

    all_signals = high + medium + low

    raw = (
        BASE_SCORE
        + len(high) * HIGH_PTS
        + len(medium) * MEDIUM_PTS
        + len(low) * LOW_PTS
        + len(conditions) * CONDITION_PTS
    )

    score = min(10, max(1, raw))

    return MotivationResult(
        score=score,
        signals=all_signals,
        conditions=conditions,
    )
