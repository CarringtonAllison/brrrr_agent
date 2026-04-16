"""Scan orchestrator — async generator yielding SSE events.

Pipeline: Scrape → Prefilter → Analysis (BRRRR + comp + rental + motivation)
Phase 6 will add AI review (concurrency=3) after this stage.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional

from backend.brrrr_calculator import run_full_analysis
from backend.comp_analyzer import estimate_arv
from backend.motivation_detector import score_motivation
from backend.prefilter import apply_prefilter
from backend.rental_estimator import estimate_rent
from backend.scrapers.scraper_manager import ScraperManager

logger = logging.getLogger(__name__)


class ScanEvent:
    """Factory methods for SSE event dicts."""

    @staticmethod
    def source_status(source: str, status: str, count: int) -> dict:
        return {"type": "source_status", "source": source, "status": status, "count": count}

    @staticmethod
    def listing(listing: dict) -> dict:
        return {"type": "listing", "listing": listing}

    @staticmethod
    def done(total: int, strong: int, good: int) -> dict:
        return {"type": "done", "summary": {"total": total, "strong": strong, "good": good}}


async def run_scan(
    market: dict,
    scraper: Optional[ScraperManager] = None,
    rental_listings: Optional[list[dict]] = None,
    sold_comps: Optional[list[dict]] = None,
) -> AsyncGenerator[dict, None]:
    """Run a full scan for a market and yield SSE events.

    Args:
        market: Market dict with name, city, state, zip_codes, etc.
        scraper: Injected ScraperManager (creates a real one if None).
        rental_listings: Pre-fetched rental comps (for testing / caching).
        sold_comps: Pre-fetched sold comps for ARV (for testing / caching).
    """
    if scraper is None:
        scraper = ScraperManager()

    target_beds = 3  # default; could be derived from market config

    # ── Stage 1: Scrape ───────────────────────────────────────────────────────
    yield ScanEvent.source_status("redfin", "scraping", 0)

    raw_listings: list[dict] = []
    try:
        raw_listings = scraper.scrape_market(market)
        yield ScanEvent.source_status("redfin", "done", len(raw_listings))
    except Exception as exc:
        logger.error(f"Scraper failed for {market.get('name')}: {exc}")
        yield ScanEvent.source_status("redfin", "error", 0)

    # ── Stage 2: Prefilter + Analyze ──────────────────────────────────────────
    total = 0
    strong = 0
    good = 0

    # Use empty lists when not provided (ARV from fallback, no rental data)
    comps = sold_comps or []
    rentals = rental_listings or []

    for listing in raw_listings:
        passed, reason = apply_prefilter(listing)
        if not passed:
            logger.debug(f"Prefilter rejected {listing.get('address')}: {reason}")
            continue

        # ARV estimation from sold comps
        subject = {
            "sqft": listing.get("sqft"),
            "beds": listing.get("beds"),
            "baths": listing.get("baths"),
        }
        arv_result = estimate_arv(comps, subject)
        arv = arv_result.arv

        # If no comps, estimate ARV as a rough multiple of price
        if arv is None:
            price = listing.get("price", 0) or 0
            arv = price * 1.30  # assume 30% uplift as fallback

        # Rental estimate
        beds = listing.get("beds") or target_beds
        rent_result = estimate_rent(rentals, target_beds=beds, arv=arv)
        estimated_rent = rent_result.estimated_rent or 0.0

        # BRRRR analysis
        price = listing.get("price", 0) or 0
        brrrr = run_full_analysis(
            purchase_price=price,
            arv=arv,
            estimated_rent=estimated_rent,
        )

        # Motivation score
        motivation = score_motivation(listing)

        # Enrich listing with analysis results
        enriched = dict(listing)
        enriched["grade"] = brrrr.grade
        enriched["motivation_score"] = motivation.score
        enriched["motivation_signals"] = motivation.signals
        enriched["arv"] = arv
        enriched["estimated_rent"] = estimated_rent
        enriched["brrrr"] = {
            "cash_left_in_deal": brrrr.cash_left_in_deal,
            "monthly_cashflow": brrrr.monthly_cashflow,
            "coc_return": brrrr.coc_return,
            "dscr": brrrr.dscr,
            "rent_to_price": brrrr.rent_to_price,
            "seventy_pct_rule_pass": brrrr.seventy_pct_rule_pass,
            "grade": brrrr.grade,
            "grade_reasons": brrrr.grade_reasons,
        }

        total += 1
        if brrrr.grade == "STRONG":
            strong += 1
        elif brrrr.grade == "GOOD":
            good += 1

        yield ScanEvent.listing(enriched)

    yield ScanEvent.done(total=total, strong=strong, good=good)
