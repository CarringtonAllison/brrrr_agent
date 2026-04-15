"""Tests for scraper manager — deduplication, merging, orchestration."""

import pytest

from backend.scrapers.scraper_manager import (
    deduplicate_listings,
    merge_listing_data,
)


def _listing(source: str, address: str, **kwargs) -> dict:
    """Helper to build a listing dict."""
    base = {
        "source": source,
        "source_id": f"{source}_1",
        "address": address,
        "normalized_address": "",
        "city": "Cleveland",
        "state": "OH",
        "zip_code": "44108",
        "price": 65_000,
        "beds": 3,
        "baths": 1,
        "sqft": 1100,
        "year_built": None,
        "property_type": "single family",
        "description": "",
        "days_on_market": None,
        "latitude": None,
        "longitude": None,
        "listing_url": "",
    }
    base.update(kwargs)
    return base


class TestDeduplicateListings:
    def test_no_duplicates(self):
        listings = [
            _listing("redfin", "123 Main St"),
            _listing("redfin", "456 Oak Ave", source_id="rf_2"),
        ]
        result = deduplicate_listings(listings)
        assert len(result) == 2

    def test_exact_duplicate_keeps_redfin(self):
        """Same address from Redfin and Craigslist — keep Redfin."""
        listings = [
            _listing("redfin", "123 Main St", sqft=1100, year_built=1952),
            _listing("craigslist", "123 Main St", sqft=None, year_built=None),
        ]
        result = deduplicate_listings(listings)
        assert len(result) == 1
        assert result[0]["source"] == "redfin"
        assert result[0]["sqft"] == 1100

    def test_fuzzy_duplicate(self):
        """Similar addresses (St vs Street) should dedup."""
        listings = [
            _listing("redfin", "123 Main St"),
            _listing("craigslist", "123 Main Street"),
        ]
        result = deduplicate_listings(listings)
        assert len(result) == 1

    def test_three_sources_dedup(self):
        """Same property from all three sources → one merged result."""
        listings = [
            _listing("redfin", "123 Main St", sqft=1100, year_built=1952),
            _listing("craigslist", "123 Main St", description="Estate sale as-is"),
            _listing("zillow", "123 Main St", sqft=1100),
        ]
        result = deduplicate_listings(listings)
        assert len(result) == 1

    def test_different_addresses_not_deduped(self):
        listings = [
            _listing("redfin", "123 Main St"),
            _listing("redfin", "456 Oak Ave", source_id="rf_2"),
        ]
        result = deduplicate_listings(listings)
        assert len(result) == 2


class TestMergeListingData:
    def test_redfin_preferred_for_numerics(self):
        """Redfin data preferred for structured fields (sqft, year_built)."""
        redfin = _listing("redfin", "123 Main St", sqft=1100, year_built=1952)
        craigslist = _listing("craigslist", "123 Main St", sqft=None, year_built=None,
                             description="Great estate sale property, as-is condition")

        merged = merge_listing_data(redfin, craigslist)
        assert merged["sqft"] == 1100
        assert merged["year_built"] == 1952
        assert "estate sale" in merged["description"].lower()

    def test_craigslist_preferred_for_description(self):
        """Craigslist descriptions are richer — prefer them."""
        redfin = _listing("redfin", "123 Main St", description="")
        craigslist = _listing("craigslist", "123 Main St",
                             description="Motivated seller, estate sale, cash only, needs work")

        merged = merge_listing_data(redfin, craigslist)
        assert "motivated seller" in merged["description"].lower()

    def test_keeps_all_source_urls(self):
        """Merged listing should track URLs from all sources."""
        redfin = _listing("redfin", "123 Main St", listing_url="https://redfin.com/123")
        zillow = _listing("zillow", "123 Main St", listing_url="https://zillow.com/123")

        merged = merge_listing_data(redfin, zillow)
        assert "redfin.com" in merged["listing_url"]
        assert "zillow.com" in str(merged.get("alt_urls", []))
