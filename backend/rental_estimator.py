"""Rental estimator — market-based median rent with IQR outlier removal.

Sources Craigslist rental listings scraped for the market.
7-day data is used as-is (cache freshness enforced by the orchestrator).
Fallback: 1.1% of ARV / 12 months when no rental data is available.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Optional

FALLBACK_RATE = 0.011  # 1.1% of ARV monthly (the "1% rule" variant)
BED_TOLERANCE = 1       # include beds ±1 from target when filtering


# ── IQR outlier removal ───────────────────────────────────────────────────────

def remove_outliers_iqr(prices: list[float]) -> list[float]:
    """Remove outliers using the IQR method (1.5 × IQR fence).

    Returns the filtered list. Input is not modified.
    """
    if len(prices) <= 2:
        return list(prices)

    sorted_p = sorted(prices)
    n = len(sorted_p)

    q1 = sorted_p[n // 4]
    q3 = sorted_p[(3 * n) // 4]
    iqr = q3 - q1

    fence_low = q1 - 1.5 * iqr
    fence_high = q3 + 1.5 * iqr

    return [p for p in sorted_p if fence_low <= p <= fence_high]


# ── Market-based estimate ─────────────────────────────────────────────────────

def estimate_rent_from_listings(
    rentals: list[dict],
    target_beds: int,
) -> Optional[float]:
    """Estimate market rent from Craigslist rental listings.

    Filters to target_beds ±1, removes IQR outliers, returns the median.
    Returns None if no matching listings found.
    """
    if not rentals:
        return None

    # Filter by bed count (exact first; widen to ±1 if needed)
    exact = [r for r in rentals if r.get("beds") == target_beds and r.get("price")]
    adjacent = [
        r for r in rentals
        if r.get("beds") is not None
        and abs(r["beds"] - target_beds) <= BED_TOLERANCE
        and r.get("price")
    ]

    pool = exact if len(exact) >= 3 else adjacent
    if not pool:
        return None

    prices = [float(r["price"]) for r in pool]
    filtered = remove_outliers_iqr(prices)
    if not filtered:
        return None

    return statistics.median(filtered)


# ── Fallback estimator ────────────────────────────────────────────────────────

def estimate_rent_fallback(arv: float) -> float:
    """Estimate rent using the 1.1% annual gross yield rule (monthly).

    fallback_rent = arv * 0.011
    """
    return arv * FALLBACK_RATE


# ── Full pipeline ─────────────────────────────────────────────────────────────

@dataclass
class RentalEstimate:
    estimated_rent: Optional[float]
    source: str          # "market", "fallback", or "none"
    sample_count: int


def estimate_rent(
    rentals: list[dict],
    target_beds: int,
    arv: Optional[float],
) -> RentalEstimate:
    """Estimate monthly rent for a subject property.

    1. Try market data (Craigslist rentals).
    2. Fall back to ARV-based rule if no data.
    3. Return source="none" if neither is available.
    """
    market_rent = estimate_rent_from_listings(rentals, target_beds)
    if market_rent is not None:
        # Count the clean sample used
        exact = [r for r in rentals if r.get("beds") == target_beds and r.get("price")]
        adjacent = [
            r for r in rentals
            if r.get("beds") is not None
            and abs(r["beds"] - target_beds) <= BED_TOLERANCE
            and r.get("price")
        ]
        pool = exact if len(exact) >= 3 else adjacent
        prices = [float(r["price"]) for r in pool]
        clean_prices = remove_outliers_iqr(prices)
        return RentalEstimate(
            estimated_rent=market_rent,
            source="market",
            sample_count=len(clean_prices),
        )

    if arv is not None and arv > 0:
        return RentalEstimate(
            estimated_rent=estimate_rent_fallback(arv),
            source="fallback",
            sample_count=0,
        )

    return RentalEstimate(estimated_rent=None, source="none", sample_count=0)
