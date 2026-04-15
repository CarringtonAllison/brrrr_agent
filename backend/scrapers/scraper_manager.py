"""Scraper manager — orchestrates all scrapers, deduplicates, and merges results.

Run order: Redfin (most reliable) → Craigslist → Zillow (most fragile).
Deduplication uses normalized addresses + fuzzy matching.
Merge prefers Redfin for numeric fields, Craigslist for descriptions.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from backend.database import normalize_address, fuzzy_match
from backend.scrapers.redfin_api import RedfinScraper
from backend.scrapers.craigslist_rss import CraigslistScraper

logger = logging.getLogger(__name__)

SOURCE_PRIORITY = {"redfin": 0, "zillow": 1, "craigslist": 2}


def deduplicate_listings(listings: list[dict]) -> list[dict]:
    """Deduplicate listings across sources using normalized address + fuzzy matching.

    When duplicates are found, merges data preferring higher-priority sources.
    Priority: redfin > zillow > craigslist (for structured data).
    """
    # Normalize all addresses
    for listing in listings:
        listing["normalized_address"] = normalize_address(listing.get("address", ""))

    # Group by normalized address using fuzzy matching
    groups: list[list[dict]] = []
    used = set()

    for i, listing in enumerate(listings):
        if i in used:
            continue

        group = [listing]
        used.add(i)

        for j in range(i + 1, len(listings)):
            if j in used:
                continue
            if (
                listing["zip_code"] == listings[j]["zip_code"]
                and fuzzy_match(
                    listing["normalized_address"],
                    normalize_address(listings[j].get("address", "")),
                )
            ):
                group.append(listings[j])
                used.add(j)

        groups.append(group)

    # Merge each group into a single listing
    merged = []
    for group in groups:
        if len(group) == 1:
            merged.append(group[0])
        else:
            # Sort by source priority (best first)
            group.sort(key=lambda x: SOURCE_PRIORITY.get(x["source"], 99))
            result = group[0]  # start with best source
            for other in group[1:]:
                result = merge_listing_data(result, other)
            merged.append(result)

    return merged


def merge_listing_data(primary: dict, secondary: dict) -> dict:
    """Merge two listing dicts for the same property.

    Primary is the higher-priority source (usually Redfin).
    Secondary fills in missing data (usually Craigslist for description).
    """
    merged = dict(primary)

    # Fill missing numeric fields from secondary
    for field in ("sqft", "year_built", "beds", "baths", "days_on_market", "latitude", "longitude"):
        if merged.get(field) is None and secondary.get(field) is not None:
            merged[field] = secondary[field]

    # Prefer longer/richer description (Craigslist typically has better text)
    primary_desc = merged.get("description", "") or ""
    secondary_desc = secondary.get("description", "") or ""
    if len(secondary_desc) > len(primary_desc):
        merged["description"] = secondary_desc

    # Track alternative listing URLs
    alt_urls = merged.get("alt_urls", [])
    if secondary.get("listing_url"):
        alt_urls.append(secondary["listing_url"])
    merged["alt_urls"] = alt_urls

    return merged


class ScraperManager:
    """Orchestrates all scrapers for a market, deduplicates results."""

    def __init__(self):
        self.redfin = RedfinScraper()
        self.craigslist = CraigslistScraper()

    def scrape_market(self, market: dict) -> list[dict]:
        """Run all scrapers for a market and return deduplicated listings.

        Args:
            market: dict with keys: name, city, state, craigslist_subdomain,
                    redfin_region_id, redfin_region_type, zip_codes
        """
        all_listings = []
        health = []

        # Redfin (most reliable, run first)
        try:
            redfin_listings = self.redfin.get_active_listings(market)
            all_listings.extend(redfin_listings)
            health.append({"source": "redfin", "count": len(redfin_listings), "error": None})
            logger.info(f"Redfin: {len(redfin_listings)} listings for {market['name']}")
        except Exception as e:
            health.append({"source": "redfin", "count": 0, "error": str(e)})
            logger.error(f"Redfin failed for {market['name']}: {e}")

        # Craigslist
        try:
            cl_subdomain = market.get("craigslist_subdomain", "")
            if cl_subdomain:
                cl_listings = self.craigslist.get_for_sale_listings(cl_subdomain)
                all_listings.extend(cl_listings)
                health.append({"source": "craigslist", "count": len(cl_listings), "error": None})
                logger.info(f"Craigslist: {len(cl_listings)} listings for {market['name']}")
        except Exception as e:
            health.append({"source": "craigslist", "count": 0, "error": str(e)})
            logger.error(f"Craigslist failed for {market['name']}: {e}")

        # Zillow is async — handled separately by the orchestrator
        # (scraper_manager stays synchronous for simplicity)

        # Deduplicate across sources
        deduplicated = deduplicate_listings(all_listings)
        logger.info(
            f"Market {market['name']}: {len(all_listings)} raw → {len(deduplicated)} after dedup"
        )

        return deduplicated
