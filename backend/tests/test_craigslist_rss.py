"""Tests for Craigslist RSS scraper — feed parsing, URL building, listing extraction."""

import pytest
from unittest.mock import patch, MagicMock

from backend.scrapers.craigslist_rss import (
    build_for_sale_rss_url,
    build_rental_rss_url,
    parse_rss_feed,
    extract_listing_from_page,
    CraigslistScraper,
)


# ── Sample RSS XML ──────────────────────────────────────────────────────────

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns="http://purl.org/rss/1.0/"
         xmlns:dc="http://purl.org/dc/elements/1.1/"
         xmlns:enc="http://purl.oclc.org/net/rss_2.0/enc#">
<channel>
<title>craigslist birmingham | real estate - by owner</title>
</channel>
<item rdf:about="https://birmingham.craigslist.org/rea/d/birmingham-investor-special/7800001.html">
<title>$65000 3br - 1100ft2 - Investor Special - 123 Main St (Birmingham)</title>
<link>https://birmingham.craigslist.org/rea/d/birmingham-investor-special/7800001.html</link>
<description>Investor special! As-is estate sale. 3br/1ba, 1100 sqft. Needs work but great bones.</description>
<dc:date>2026-04-10T08:00:00-05:00</dc:date>
</item>
<item rdf:about="https://birmingham.craigslist.org/rea/d/birmingham-fixer-upper/7800002.html">
<title>$48000 2br - 900ft2 - Fixer Upper (Bessemer)</title>
<link>https://birmingham.craigslist.org/rea/d/birmingham-fixer-upper/7800002.html</link>
<description>Handyman special. Cash only. Vacant and ready for rehab.</description>
<dc:date>2026-04-09T10:00:00-05:00</dc:date>
</item>
</rdf:RDF>"""

# ── Sample listing page HTML ───────────────────────────────────────────────

SAMPLE_PAGE_HTML = """
<html>
<body>
<section id="postingbody">
  Investor special! This estate sale property at 123 Main St, Birmingham AL 35208
  is perfect for BRRRR investors. As-is condition. 3 bedrooms, 1 bathroom.
  Approximately 1100 sqft. Built in 1952. Cash offers preferred.
</section>
<p class="attrgroup">
  <span>3BR / 1Ba</span>
  <span>1100ft2</span>
  <span>available now</span>
</p>
<div class="mapaddress">123 Main St, Birmingham, AL 35208</div>
</body>
</html>"""


class TestBuildUrls:
    def test_for_sale_url(self):
        url = build_for_sale_rss_url("birmingham")
        assert "birmingham.craigslist.org" in url
        assert "format=rss" in url
        assert "max_price=100000" in url
        assert "min_bedrooms=2" in url
        assert "housing_type=6" in url

    def test_rental_url(self):
        url = build_rental_rss_url("birmingham")
        assert "birmingham.craigslist.org" in url
        assert "/search/apa" in url
        assert "format=rss" in url


class TestParseRssFeed:
    def test_parses_two_entries(self):
        entries = parse_rss_feed(SAMPLE_RSS)
        assert len(entries) == 2

    def test_entry_fields(self):
        entries = parse_rss_feed(SAMPLE_RSS)
        first = entries[0]
        assert "title" in first
        assert "link" in first
        assert "description" in first

    def test_extracts_price_from_title(self):
        entries = parse_rss_feed(SAMPLE_RSS)
        assert entries[0]["price"] == 65_000
        assert entries[1]["price"] == 48_000

    def test_extracts_beds_from_title(self):
        entries = parse_rss_feed(SAMPLE_RSS)
        assert entries[0]["beds"] == 3
        assert entries[1]["beds"] == 2

    def test_extracts_sqft_from_title(self):
        entries = parse_rss_feed(SAMPLE_RSS)
        assert entries[0]["sqft"] == 1100
        assert entries[1]["sqft"] == 900

    def test_empty_feed(self):
        empty = '<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><channel/></rdf:RDF>'
        entries = parse_rss_feed(empty)
        assert entries == []


class TestExtractFromPage:
    def test_extracts_address(self):
        data = extract_listing_from_page(SAMPLE_PAGE_HTML)
        assert data["address"] == "123 Main St, Birmingham, AL 35208"

    def test_extracts_description(self):
        data = extract_listing_from_page(SAMPLE_PAGE_HTML)
        assert "investor special" in data["description"].lower()

    def test_handles_missing_address(self):
        html = "<html><body><section id='postingbody'>No address here</section></body></html>"
        data = extract_listing_from_page(html)
        assert data["address"] == ""


class TestCraigslistScraper:
    @patch("backend.scrapers.craigslist_rss.requests.Session.get")
    def test_get_for_sale_listings(self, mock_get):
        """Scraper should parse RSS feed and return standardized listings."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_RSS
        mock_get.return_value = mock_resp

        scraper = CraigslistScraper(fetch_individual_pages=False)
        listings = scraper.get_for_sale_listings("birmingham")
        assert len(listings) == 2
        assert listings[0]["source"] == "craigslist"
        assert listings[0]["price"] == 65_000
        assert listings[0]["beds"] == 3
        assert listings[0]["source_id"] == "7800001"
