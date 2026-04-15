"""Pre-filter for raw listings.

Applies fast boolean checks before any expensive analysis.
Returns (passed, reason) where reason explains rejection.
"""

from __future__ import annotations

MAX_PRICE = 100_000
MIN_PRICE = 25_000
MIN_BEDS = 2
MAX_BEDS = 5
MIN_SQFT = 700
MAX_DOM = 120
ALLOWED_TYPES = {"single family", "townhouse"}


def apply_prefilter(listing: dict) -> tuple[bool, str]:
    """Check a raw listing against all pre-filter criteria.

    Returns (passed, reason). If passed is True, reason is empty.
    Checks run in order; first failure short-circuits.
    """
    price = listing.get("price")
    if price is None:
        return False, "No price listed"
    if price < MIN_PRICE:
        return False, f"Price ${price:,.0f} below ${MIN_PRICE:,} minimum"
    if price > MAX_PRICE:
        return False, f"Price ${price:,.0f} above ${MAX_PRICE:,} maximum"

    beds = listing.get("beds")
    if beds is not None:
        if beds < MIN_BEDS:
            return False, f"{beds} beds below {MIN_BEDS} minimum"
        if beds > MAX_BEDS:
            return False, f"{beds} beds above {MAX_BEDS} maximum"

    prop_type = listing.get("property_type")
    if prop_type is not None:
        if prop_type.lower() not in ALLOWED_TYPES:
            return False, f"Property type '{prop_type}' not in allowed types"

    sqft = listing.get("sqft")
    if sqft is not None and sqft < MIN_SQFT:
        return False, f"{sqft} sqft below {MIN_SQFT} minimum"

    dom = listing.get("days_on_market")
    if dom is not None and dom > MAX_DOM:
        return False, f"{dom} days on market exceeds {MAX_DOM} day maximum"

    return True, ""
