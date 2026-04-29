"""Scan orchestrator — async generator yielding SSE events.

Pipeline:
  1. Scrape (Redfin / Craigslist / Zillow via ScraperManager)
  2. Prefilter listings
  3. Per-listing math: BRRRR, comps, rental, motivation
  4. Per-listing AI review (Sonnet) + negotiation advice (Haiku) — concurrency=3
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any, AsyncGenerator, Optional

from backend.agents.deal_analyst import review_deal
from backend.agents.negotiation_agent import suggest_offer
from backend.brrrr_calculator import run_full_analysis
from backend.comp_analyzer import estimate_arv
from backend.motivation_detector import score_motivation
from backend.prefilter import apply_prefilter
from backend.rental_estimator import estimate_rent
from backend.scrapers.scraper_manager import ScraperManager

logger = logging.getLogger(__name__)


AI_REVIEW_GRADES = {"STRONG", "GOOD", "MAYBE"}
AI_CONCURRENCY = 3


class ScanEvent:
    """Factory methods for SSE event dicts."""

    @staticmethod
    def source_status(source: str, status: str, count: int) -> dict:
        return {"type": "source_status", "source": source, "status": status, "count": count}

    @staticmethod
    def listing(listing: dict) -> dict:
        return {"type": "listing", "listing": listing}

    @staticmethod
    def ai_review(listing_id: str, review: dict, negotiation: dict) -> dict:
        return {
            "type": "ai_review",
            "listing_id": listing_id,
            "review": review,
            "negotiation": negotiation,
        }

    @staticmethod
    def done(total: int, strong: int, good: int) -> dict:
        return {"type": "done", "summary": {"total": total, "strong": strong, "good": good}}


async def _run_one_review(
    enriched: dict,
    api_key: str,
    sem: asyncio.Semaphore,
    db: Any | None,
) -> dict | None:
    """Run review_deal + suggest_offer for a single listing, persist if db given.

    Returns the ai_review event dict, or None on hard failure.
    """
    async with sem:
        listing_id = enriched.get("id") or enriched.get("address") or "unknown"
        try:
            review = await asyncio.to_thread(review_deal, enriched, api_key)
        except Exception as exc:
            logger.warning(f"review_deal failed for {listing_id}: {exc}")
            return None

        try:
            advice = await asyncio.to_thread(suggest_offer, enriched, api_key)
        except Exception as exc:
            logger.warning(f"suggest_offer failed for {listing_id}: {exc}")
            advice = None

        review_dict = asdict(review)
        advice_dict = asdict(advice) if advice is not None else {}

        if db is not None and enriched.get("id"):
            try:
                db.update_analysis(
                    enriched["id"],
                    ai_review=review_dict,
                    ai_summary=review_dict.get("summary"),
                    negotiation_advice=advice_dict or None,
                )
            except Exception as exc:
                logger.warning(f"DB persistence failed for {listing_id}: {exc}")

        return ScanEvent.ai_review(listing_id, review_dict, advice_dict)


async def run_scan(
    market: dict,
    scraper: Optional[ScraperManager] = None,
    rental_listings: Optional[list[dict]] = None,
    sold_comps: Optional[list[dict]] = None,
    api_key: str = "",
    db: Any | None = None,
) -> AsyncGenerator[dict, None]:
    """Run a full scan for a market and yield SSE events.

    Args:
        market: Market dict with name, city, state, zip_codes, etc.
        scraper: Injected ScraperManager (creates a real one if None).
        rental_listings: Pre-fetched rental comps (for testing / caching).
        sold_comps: Pre-fetched sold comps for ARV (for testing / caching).
        api_key: Anthropic API key. Empty string disables AI review.
        db: Optional Database instance for persisting analysis.
    """
    if scraper is None:
        scraper = ScraperManager()

    target_beds = 3

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

    comps = sold_comps or []
    rentals = rental_listings or []

    reviewable: list[dict] = []  # listings eligible for AI review

    for listing in raw_listings:
        passed, reason = apply_prefilter(listing)
        if not passed:
            logger.debug(f"Prefilter rejected {listing.get('address')}: {reason}")
            continue

        subject = {
            "sqft": listing.get("sqft"),
            "beds": listing.get("beds"),
            "baths": listing.get("baths"),
        }
        arv_result = estimate_arv(comps, subject)
        arv = arv_result.arv

        if arv is None:
            price = listing.get("price", 0) or 0
            arv = price * 1.30

        beds = listing.get("beds") or target_beds
        rent_result = estimate_rent(rentals, target_beds=beds, arv=arv)
        estimated_rent = rent_result.estimated_rent or 0.0

        price = listing.get("price", 0) or 0
        brrrr = run_full_analysis(
            purchase_price=price,
            arv=arv,
            estimated_rent=estimated_rent,
        )

        motivation = score_motivation(listing)

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
            "total_all_in": brrrr.total_all_in,
            "estimated_rent": brrrr.estimated_rent,
        }

        total += 1
        if brrrr.grade == "STRONG":
            strong += 1
        elif brrrr.grade == "GOOD":
            good += 1

        # Persist BRRRR/motivation results if DB and listing.id available
        if db is not None and enriched.get("id"):
            try:
                db.update_analysis(
                    enriched["id"],
                    brrrr=enriched["brrrr"],
                    grade=brrrr.grade,
                    motivation_score=motivation.score,
                )
            except Exception as exc:
                logger.warning(f"BRRRR persistence failed: {exc}")

        yield ScanEvent.listing(enriched)

        if brrrr.grade in AI_REVIEW_GRADES:
            reviewable.append(enriched)

    # ── Stage 3: AI Review (concurrency=AI_CONCURRENCY) ───────────────────────
    if api_key and reviewable:
        sem = asyncio.Semaphore(AI_CONCURRENCY)
        tasks = [
            asyncio.create_task(_run_one_review(item, api_key, sem, db))
            for item in reviewable
        ]
        for coro in asyncio.as_completed(tasks):
            event = await coro
            if event is not None:
                yield event

    yield ScanEvent.done(total=total, strong=strong, good=good)
