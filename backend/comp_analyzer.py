"""Comp analyzer — similarity scoring, tiered filtering, and ARV estimation.

Three sources: Redfin similars/solds, GIS sold, Zillow sold.
Scoring: distance(30) + recency(25) + sqft(20) + beds(15) + baths(10) = 100
Tiered filtering: starts tight, widens until >= 3 non-distressed comps.
ARV is a score-weighted mean with conservative/aggressive percentile bounds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

# ── Distressed sale detection ─────────────────────────────────────────────────

_DISTRESSED_PATTERNS = re.compile(
    r"\b(foreclosure|foreclosed|bank[- ]?owned|reo|short[- ]?sale|auction|"
    r"as-is|as is)\b",
    re.IGNORECASE,
)


def is_distressed(comp: dict) -> bool:
    """Return True if the comp appears to be a distressed sale."""
    text = " ".join([
        comp.get("listing_type", "") or "",
        comp.get("description", "") or "",
    ])
    return bool(_DISTRESSED_PATTERNS.search(text))


# ── Similarity scoring ────────────────────────────────────────────────────────

# Weight constants (must sum to 100)
W_DISTANCE = 30
W_RECENCY = 25
W_SQFT = 20
W_BEDS = 15
W_BATHS = 10

# Max reference values for linear scaling
MAX_DISTANCE_MILES = 2.0
MAX_AGE_DAYS = 730  # 2 years
SQFT_ZERO_SCORE_RATIO = 0.50  # 50% difference → 0 sqft score


def score_comp(comp: dict, subject: dict) -> float:
    """Score a comparable sale against a subject property. Returns 0-100."""
    score = 0.0

    # Distance (30 pts): linear from 0 miles (30) to MAX_DISTANCE (0)
    dist = comp.get("distance_miles") or 0.0
    score += W_DISTANCE * max(0.0, 1.0 - dist / MAX_DISTANCE_MILES)

    # Recency (25 pts): linear from 0 days (25) to MAX_AGE_DAYS (0)
    sold_date_str = comp.get("sold_date")
    if sold_date_str:
        try:
            sold = date.fromisoformat(sold_date_str)
            days_ago = (date.today() - sold).days
            score += W_RECENCY * max(0.0, 1.0 - days_ago / MAX_AGE_DAYS)
        except (ValueError, TypeError):
            pass  # no recency credit if date unparseable

    # Sqft (20 pts): full credit at exact match, 0 at >= 50% difference
    subject_sqft = subject.get("sqft")
    comp_sqft = comp.get("sqft")
    if subject_sqft and comp_sqft:
        diff_ratio = abs(subject_sqft - comp_sqft) / subject_sqft
        score += W_SQFT * max(0.0, 1.0 - diff_ratio / SQFT_ZERO_SCORE_RATIO)
    else:
        score += W_SQFT * 0.5  # half credit when sqft unknown

    # Beds (15 pts): 15 exact, -5 per bedroom difference, min 0
    subject_beds = subject.get("beds")
    comp_beds = comp.get("beds")
    if subject_beds is not None and comp_beds is not None:
        score += max(0.0, W_BEDS - 5 * abs(subject_beds - comp_beds))
    else:
        score += W_BEDS * 0.5

    # Baths (10 pts): 10 exact, -5 per 0.5-bath increment difference, min 0
    subject_baths = subject.get("baths")
    comp_baths = comp.get("baths")
    if subject_baths is not None and comp_baths is not None:
        half_bath_diff = abs(subject_baths - comp_baths) / 0.5
        score += max(0.0, W_BATHS - 5 * half_bath_diff)
    else:
        score += W_BATHS * 0.5

    return min(100.0, max(0.0, score))


# ── Tiered filtering ──────────────────────────────────────────────────────────

_TIERS = [
    # (max_distance_miles, max_age_days, max_sqft_diff_ratio)
    (0.5, 180, 0.20),   # Tier 1: tight
    (1.0, 365, 0.30),   # Tier 2: medium
    (2.0, 730, 0.40),   # Tier 3: wide
]
MIN_COMPS = 3


def _passes_tier(comp: dict, subject: dict, tier_idx: int) -> bool:
    max_dist, max_age, max_sqft_diff = _TIERS[tier_idx]

    dist = comp.get("distance_miles") or 0.0
    if dist > max_dist:
        return False

    sold_date_str = comp.get("sold_date")
    if sold_date_str:
        try:
            sold = date.fromisoformat(sold_date_str)
            if (date.today() - sold).days > max_age:
                return False
        except (ValueError, TypeError):
            pass

    subject_sqft = subject.get("sqft")
    comp_sqft = comp.get("sqft")
    if subject_sqft and comp_sqft:
        diff_ratio = abs(subject_sqft - comp_sqft) / subject_sqft
        if diff_ratio > max_sqft_diff:
            return False

    return True


def filter_comps_tiered(comps: list[dict], subject: dict) -> tuple[list[dict], int]:
    """Filter comps using tiered criteria, widening until >= MIN_COMPS remain.

    Returns (filtered_comps, tier_number) where tier_number is 1, 2, or 3.
    Distressed comps are excluded at all tiers.
    """
    clean = [c for c in comps if not is_distressed(c)]

    for tier_idx, _ in enumerate(_TIERS):
        filtered = [c for c in clean if _passes_tier(c, subject, tier_idx)]
        if len(filtered) >= MIN_COMPS:
            return (filtered, tier_idx + 1)

    # Return all clean comps at widest tier even if < MIN_COMPS
    return (clean, 3)


# ── ARV estimation ────────────────────────────────────────────────────────────

@dataclass
class ARVEstimate:
    arv: Optional[float]            # score-weighted mean price
    arv_conservative: Optional[float]  # 25th percentile
    arv_aggressive: Optional[float]    # 75th percentile
    comp_count: int
    comps_used: list[dict] = field(default_factory=list)
    filter_tier: int = 3


def _weighted_percentile(values: list[float], weights: list[float], p: float) -> float:
    """Compute weighted percentile using linear interpolation."""
    if not values:
        raise ValueError("Empty values")

    paired = sorted(zip(values, weights), key=lambda x: x[0])
    sorted_vals = [v for v, _ in paired]
    sorted_weights = [w for _, w in paired]

    total = sum(sorted_weights)
    cumulative = 0.0
    for i, (val, w) in enumerate(zip(sorted_vals, sorted_weights)):
        cumulative += w / total
        if cumulative >= p:
            return val

    return sorted_vals[-1]


def estimate_arv(comps: list[dict], subject: dict) -> ARVEstimate:
    """Estimate ARV from comparable sales.

    Returns ARVEstimate with score-weighted mean and conservative/aggressive bounds.
    """
    filtered, tier = filter_comps_tiered(comps, subject)

    if not filtered:
        return ARVEstimate(arv=None, arv_conservative=None, arv_aggressive=None,
                           comp_count=0, comps_used=[], filter_tier=tier)

    prices = [c["price"] for c in filtered if c.get("price")]
    scored = [(c, score_comp(c, subject)) for c in filtered if c.get("price")]

    if not scored:
        return ARVEstimate(arv=None, arv_conservative=None, arv_aggressive=None,
                           comp_count=0, comps_used=filtered, filter_tier=tier)

    # Score-weighted mean
    total_weight = sum(s for _, s in scored)
    if total_weight == 0:
        # All scores are zero — fall back to simple mean
        arv = sum(c["price"] for c, _ in scored) / len(scored)
    else:
        arv = sum(c["price"] * s for c, s in scored) / total_weight

    # Percentile bounds
    vals = [c["price"] for c, _ in scored]
    weights = [max(s, 0.01) for _, s in scored]  # avoid zero-weight edge case
    arv_conservative = _weighted_percentile(vals, weights, 0.25)
    arv_aggressive = _weighted_percentile(vals, weights, 0.75)

    return ARVEstimate(
        arv=arv,
        arv_conservative=arv_conservative,
        arv_aggressive=arv_aggressive,
        comp_count=len(scored),
        comps_used=[c for c, _ in scored],
        filter_tier=tier,
    )
