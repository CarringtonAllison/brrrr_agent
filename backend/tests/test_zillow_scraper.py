"""Tests for Zillow scraper — DOM parsing, Cloudflare detection, URL building."""

import pytest

from backend.scrapers.zillow_scraper import (
    build_search_url,
    extract_listings_from_html,
    is_cloudflare_challenge,
    ZillowScraper,
)


# ── Sample Zillow listing card HTML (simplified) ───────────────────────────

SAMPLE_CARDS_HTML = """
<html>
<body>
<ul class="List-c11n-8-109-0__sc-13e3h2g-0">
  <li>
    <article data-test="property-card">
      <address data-test="property-card-addr">123 Main St, Cleveland, OH 44108</address>
      <span data-test="property-card-price">$65,000</span>
      <ul class="StyledPropertyCardHomeDetailsList-c11n">
        <li><b>3</b> bds</li>
        <li><b>1</b> ba</li>
        <li><b>1,100</b> sqft</li>
      </ul>
      <a class="property-card-link" href="/homedetails/123-Main-St-Cleveland-OH-44108/12345_zpid/"></a>
    </article>
  </li>
  <li>
    <article data-test="property-card">
      <address data-test="property-card-addr">456 Oak Ave, Cleveland, OH 44108</address>
      <span data-test="property-card-price">$78,000</span>
      <ul class="StyledPropertyCardHomeDetailsList-c11n">
        <li><b>3</b> bds</li>
        <li><b>2</b> ba</li>
        <li><b>1,400</b> sqft</li>
      </ul>
      <a class="property-card-link" href="/homedetails/456-Oak-Ave-Cleveland-OH-44108/22222_zpid/"></a>
    </article>
  </li>
</ul>
</body>
</html>"""

CLOUDFLARE_HTML = """
<html>
<head><title>Just a moment...</title></head>
<body>
<div id="challenge-running">Checking if the site connection is secure</div>
</body>
</html>"""


class TestBuildSearchUrl:
    def test_basic_url(self):
        url = build_search_url("Cleveland", "OH", max_price=100_000)
        assert "cleveland" in url.lower()
        assert "oh" in url.lower()

    def test_includes_price_filter(self):
        url = build_search_url("Cleveland", "OH", max_price=100_000)
        assert "100000" in url


class TestExtractListingsFromHtml:
    def test_extracts_two_listings(self):
        listings = extract_listings_from_html(SAMPLE_CARDS_HTML)
        assert len(listings) == 2

    def test_listing_fields(self):
        listings = extract_listings_from_html(SAMPLE_CARDS_HTML)
        first = listings[0]
        assert first["source"] == "zillow"
        assert first["address"] == "123 Main St, Cleveland, OH 44108"
        assert first["price"] == 65_000
        assert first["beds"] == 3
        assert first["baths"] == 1
        assert first["sqft"] == 1100
        assert "zillow.com" in first["listing_url"]

    def test_empty_html(self):
        listings = extract_listings_from_html("<html><body></body></html>")
        assert listings == []


class TestCloudflareDetection:
    def test_detects_challenge(self):
        assert is_cloudflare_challenge(CLOUDFLARE_HTML) is True

    def test_normal_page(self):
        assert is_cloudflare_challenge(SAMPLE_CARDS_HTML) is False

    def test_title_check(self):
        assert is_cloudflare_challenge("<html><head><title>Just a moment...</title></head></html>") is True
