"""Craigslist RSS scraper — for-sale and rental listings.

Uses feedparser for RSS and BeautifulSoup for individual listing pages.
No Playwright needed — Craigslist serves RSS as plain XML.
"""

from __future__ import annotations

import logging
import random
import re
import time
from urllib.parse import urlencode

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def build_for_sale_rss_url(subdomain: str) -> str:
    """Build Craigslist RSS URL for for-sale real estate listings."""
    params = urlencode({
        "format": "rss",
        "max_price": "100000",
        "min_bedrooms": "2",
        "hasPic": "1",
        "housing_type": "6",  # houses only
    })
    return f"https://{subdomain}.craigslist.org/search/rea?{params}"


def build_rental_rss_url(subdomain: str) -> str:
    """Build Craigslist RSS URL for rental listings (for rent estimation)."""
    params = urlencode({
        "format": "rss",
        "min_bedrooms": "2",
        "hasPic": "1",
        "housing_type": "6",
    })
    return f"https://{subdomain}.craigslist.org/search/apa?{params}"


def parse_rss_feed(xml_text: str) -> list[dict]:
    """Parse a Craigslist RSS feed and extract listing basics from titles.

    Craigslist titles follow the pattern: $PRICE BEDSbr - SQFTft2 - TITLE (AREA)
    """
    feed = feedparser.parse(xml_text)
    entries = []

    for entry in feed.entries:
        title = getattr(entry, "title", "")
        parsed = {
            "title": title,
            "link": getattr(entry, "link", ""),
            "description": getattr(entry, "summary", getattr(entry, "description", "")),
            "price": _extract_price(title),
            "beds": _extract_beds(title),
            "sqft": _extract_sqft(title),
        }
        entries.append(parsed)

    return entries


def extract_listing_from_page(html: str) -> dict:
    """Extract detailed listing data from an individual Craigslist listing page."""
    soup = BeautifulSoup(html, "lxml")

    # Address
    addr_el = soup.find("div", class_="mapaddress")
    address = addr_el.get_text(strip=True) if addr_el else ""

    # Description
    body_el = soup.find("section", id="postingbody")
    description = body_el.get_text(strip=True) if body_el else ""

    return {
        "address": address,
        "description": description,
    }


class CraigslistScraper:
    """Scrapes Craigslist for-sale and rental listings via RSS feeds."""

    def __init__(
        self,
        delay_range: tuple[float, float] = (2, 5),
        fetch_individual_pages: bool = True,
    ):
        self.delay_range = delay_range
        self.fetch_individual_pages = fetch_individual_pages
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

    def get_for_sale_listings(self, subdomain: str) -> list[dict]:
        """Fetch for-sale listings from Craigslist RSS."""
        url = build_for_sale_rss_url(subdomain)
        return self._scrape_feed(url, listing_type="for_sale")

    def get_rental_listings(self, subdomain: str) -> list[dict]:
        """Fetch rental listings from Craigslist RSS (for rent estimation)."""
        url = build_rental_rss_url(subdomain)
        return self._scrape_feed(url, listing_type="rental")

    def _scrape_feed(self, url: str, listing_type: str) -> list[dict]:
        """Fetch and parse an RSS feed, optionally enriching with page data."""
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"Craigslist returned {resp.status_code} for {url}")
                return []
        except Exception as e:
            logger.error(f"Craigslist feed fetch failed: {e}")
            return []

        entries = parse_rss_feed(resp.text)
        listings = []

        for entry in entries:
            listing = {
                "source": "craigslist",
                "source_id": _extract_cl_id(entry["link"]),
                "listing_url": entry["link"],
                "price": entry["price"],
                "beds": entry["beds"],
                "sqft": entry["sqft"],
                "description": entry.get("description", ""),
                "address": "",
                "city": "",
                "state": "",
                "zip_code": "",
                "baths": None,
                "year_built": None,
                "property_type": "single family",
                "days_on_market": None,
                "latitude": None,
                "longitude": None,
                "listing_type": listing_type,
            }

            # Optionally fetch individual page for address + full description
            if self.fetch_individual_pages and entry["link"]:
                page_data = self._fetch_listing_page(entry["link"])
                if page_data:
                    listing["address"] = page_data.get("address", "")
                    listing["description"] = page_data.get("description", listing["description"])

            listings.append(listing)

        return listings

    def _fetch_listing_page(self, url: str) -> dict | None:
        """Fetch an individual listing page and extract details."""
        try:
            time.sleep(random.uniform(*self.delay_range))
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return None
            return extract_listing_from_page(resp.text)
        except Exception as e:
            logger.error(f"Failed to fetch CL listing page: {e}")
            return None


# ── Parsing helpers ─────────────────────────────────────────────────────────

def _extract_price(title: str) -> int | None:
    """Extract price from Craigslist title like '$65000 3br - ...'."""
    match = re.search(r"\$(\d[\d,]*)", title)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def _extract_beds(title: str) -> int | None:
    """Extract bedroom count from title like '3br'."""
    match = re.search(r"(\d+)\s*br\b", title, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _extract_sqft(title: str) -> int | None:
    """Extract square footage from title like '1100ft2'."""
    match = re.search(r"(\d+)\s*ft2?\b", title, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _extract_cl_id(url: str) -> str:
    """Extract Craigslist listing ID from URL."""
    match = re.search(r"/(\d+)\.html", url)
    return match.group(1) if match else url
