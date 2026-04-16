"""Tests for the scan orchestrator — SSE event generation and phase progression."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock, patch

from backend.agents.orchestrator import run_scan, ScanEvent


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_market(name: str = "Cleveland OH") -> dict:
    return {
        "id": "mkt-1",
        "name": name,
        "city": "Cleveland",
        "state": "OH",
        "zip_codes": ["44101", "44102"],
        "craigslist_subdomain": "cleveland",
        "redfin_region_id": "12345",
        "redfin_region_type": "2",
    }


def make_listing(
    address: str = "123 Elm St",
    price: float = 65_000,
    beds: int = 3,
    baths: float = 1.0,
    sqft: int = 1100,
    dom: int = 30,
    zip_code: str = "44101",
    property_type: str = "single family",
) -> dict:
    return {
        "address": address,
        "city": "Cleveland",
        "state": "OH",
        "zip_code": zip_code,
        "price": price,
        "beds": beds,
        "baths": baths,
        "sqft": sqft,
        "days_on_market": dom,
        "property_type": property_type,
        "source": "redfin",
        "source_id": address,
        "description": "",
        "listing_type": "",
        "listing_url": "https://redfin.com/test",
        "latitude": 41.4993,
        "longitude": -81.6944,
    }


async def collect_events(gen) -> list[dict]:
    events = []
    async for event in gen:
        events.append(event)
    return events


# ── ScanEvent structure ───────────────────────────────────────────────────────

class TestScanEvent:
    def test_source_status_event(self):
        event = ScanEvent.source_status("redfin", "scraping", 0)
        assert event["type"] == "source_status"
        assert event["source"] == "redfin"
        assert event["status"] == "scraping"
        assert event["count"] == 0

    def test_listing_event(self):
        listing = make_listing()
        event = ScanEvent.listing(listing)
        assert event["type"] == "listing"
        assert event["listing"] == listing

    def test_done_event(self):
        event = ScanEvent.done(total=10, strong=2, good=3)
        assert event["type"] == "done"
        assert event["summary"]["total"] == 10
        assert event["summary"]["strong"] == 2
        assert event["summary"]["good"] == 3


# ── run_scan event flow ───────────────────────────────────────────────────────

class TestRunScanEventFlow:
    def _mock_scraper(self, listings: list[dict]):
        mock = MagicMock()
        mock.scrape_market.return_value = listings
        return mock

    def test_emits_source_status_events(self):
        listings = [make_listing()]
        scraper = self._mock_scraper(listings)
        market = make_market()

        events = asyncio.run(collect_events(run_scan(market, scraper=scraper)))
        types = [e["type"] for e in events]
        assert "source_status" in types

    def test_emits_done_event_last(self):
        scraper = self._mock_scraper([make_listing()])
        events = asyncio.run(collect_events(run_scan(make_market(), scraper=scraper)))
        assert events[-1]["type"] == "done"

    def test_emits_listing_for_passing_listing(self):
        """A listing that passes prefilter should produce a listing event."""
        listing = make_listing(price=65_000, beds=3, sqft=1100, dom=30)
        scraper = self._mock_scraper([listing])

        events = asyncio.run(collect_events(run_scan(make_market(), scraper=scraper)))
        listing_events = [e for e in events if e["type"] == "listing"]
        assert len(listing_events) >= 1

    def test_no_listing_event_for_filtered_listing(self):
        """A listing failing prefilter (e.g. too expensive) should not emit."""
        expensive = make_listing(price=500_000)  # way over $100k max
        scraper = self._mock_scraper([expensive])

        events = asyncio.run(collect_events(run_scan(make_market(), scraper=scraper)))
        listing_events = [e for e in events if e["type"] == "listing"]
        assert listing_events == []

    def test_done_summary_counts_grades(self):
        """Done event should include counts of STRONG/GOOD grades."""
        listings = [make_listing(address=f"{i} St") for i in range(3)]
        scraper = self._mock_scraper(listings)

        events = asyncio.run(collect_events(run_scan(make_market(), scraper=scraper)))
        done = events[-1]
        assert "strong" in done["summary"]
        assert "good" in done["summary"]
        assert "total" in done["summary"]

    def test_done_total_matches_listing_event_count(self):
        listings = [make_listing(address=f"{i} Main") for i in range(3)]
        scraper = self._mock_scraper(listings)

        events = asyncio.run(collect_events(run_scan(make_market(), scraper=scraper)))
        listing_count = sum(1 for e in events if e["type"] == "listing")
        done = events[-1]
        assert done["summary"]["total"] == listing_count

    def test_empty_market_still_emits_done(self):
        scraper = self._mock_scraper([])
        events = asyncio.run(collect_events(run_scan(make_market(), scraper=scraper)))
        assert events[-1]["type"] == "done"
        assert events[-1]["summary"]["total"] == 0

    def test_scraper_failure_emits_error_status(self):
        """If the scraper raises, a source_status error event should be emitted."""
        mock = MagicMock()
        mock.scrape_market.side_effect = Exception("Network error")

        events = asyncio.run(collect_events(run_scan(make_market(), scraper=mock)))
        error_events = [
            e for e in events
            if e["type"] == "source_status" and e["status"] == "error"
        ]
        assert len(error_events) >= 1

    def test_listing_event_contains_brrrr_grade(self):
        """Each listing event should include a grade field."""
        listing = make_listing(price=65_000, beds=3, sqft=1100)
        scraper = self._mock_scraper([listing])

        events = asyncio.run(collect_events(run_scan(make_market(), scraper=scraper)))
        listing_events = [e for e in events if e["type"] == "listing"]
        assert len(listing_events) >= 1
        assert "grade" in listing_events[0]["listing"]

    def test_listing_event_contains_motivation_score(self):
        listing = make_listing(price=65_000, beds=3, sqft=1100)
        scraper = self._mock_scraper([listing])

        events = asyncio.run(collect_events(run_scan(make_market(), scraper=scraper)))
        listing_events = [e for e in events if e["type"] == "listing"]
        assert len(listing_events) >= 1
        assert "motivation_score" in listing_events[0]["listing"]

    def test_event_order_source_status_before_listings(self):
        """source_status events should precede listing events."""
        listings = [make_listing()]
        scraper = self._mock_scraper(listings)

        events = asyncio.run(collect_events(run_scan(make_market(), scraper=scraper)))
        types = [e["type"] for e in events]

        # Find positions
        first_status = next((i for i, t in enumerate(types) if t == "source_status"), None)
        first_listing = next((i for i, t in enumerate(types) if t == "listing"), None)

        if first_listing is not None:
            assert first_status < first_listing
