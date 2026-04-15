"""Zillow scraper — Playwright + stealth for listing extraction.

This is the most fragile scraper. It uses headless Chromium with stealth plugins.
If Cloudflare or CAPTCHA is detected, the scraper logs the failure and returns
empty results. The pipeline continues with Redfin + Craigslist data.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def build_search_url(city: str, state: str, max_price: int = 100_000) -> str:
    """Build a Zillow search URL for for-sale houses in a city."""
    location = f"{city.lower().replace(' ', '-')}-{state.lower()}"
    return (
        f"https://www.zillow.com/{location}/"
        f"?searchQueryState=%7B%22price%22%3A%7B%22max%22%3A{max_price}%7D%2C"
        f"%22isForSaleByAgent%22%3Atrue%2C%22isForSaleByOwner%22%3Atrue%2C"
        f"%22isNewConstruction%22%3Afalse%2C%22isAuction%22%3Afalse%2C"
        f"%22homeType%22%3A%5B%22SINGLE_FAMILY%22%2C%22TOWNHOUSE%22%5D%7D"
    )


def extract_listings_from_html(html: str) -> list[dict]:
    """Extract listing data from Zillow search results HTML."""
    soup = BeautifulSoup(html, "lxml")
    cards = soup.find_all("article", attrs={"data-test": "property-card"})
    listings = []

    for card in cards:
        try:
            addr_el = card.find(attrs={"data-test": "property-card-addr"})
            price_el = card.find(attrs={"data-test": "property-card-price"})
            link_el = card.find("a", class_="property-card-link")

            address = addr_el.get_text(strip=True) if addr_el else ""
            price = _parse_price(price_el.get_text(strip=True)) if price_el else None
            url = f"https://www.zillow.com{link_el['href']}" if link_el and link_el.get("href") else ""

            # Extract beds, baths, sqft from the details list
            beds, baths, sqft = _parse_details(card)

            # Extract zpid from URL
            zpid_match = re.search(r"/(\d+)_zpid", url)
            source_id = zpid_match.group(1) if zpid_match else ""

            listings.append({
                "source": "zillow",
                "source_id": source_id,
                "address": address,
                "city": _parse_city(address),
                "state": _parse_state(address),
                "zip_code": _parse_zip(address),
                "price": price,
                "beds": beds,
                "baths": baths,
                "sqft": sqft,
                "year_built": None,
                "property_type": "single family",
                "days_on_market": None,
                "latitude": None,
                "longitude": None,
                "listing_url": url,
            })
        except Exception as e:
            logger.warning(f"Failed to parse Zillow card: {e}")
            continue

    return listings


def is_cloudflare_challenge(html: str) -> bool:
    """Detect if the page is a Cloudflare/CAPTCHA challenge."""
    lower = html.lower()
    indicators = [
        "just a moment...",
        "challenge-running",
        "cf-browser-verification",
        "checking if the site connection is secure",
    ]
    return any(indicator in lower for indicator in indicators)


class ZillowScraper:
    """Scrapes Zillow using Playwright with stealth.

    This scraper is best-effort. If Cloudflare blocks it, the pipeline
    continues with Redfin + Craigslist data.
    """

    def __init__(self, max_pages: int = 3):
        self.max_pages = max_pages

    async def get_active_listings(self, city: str, state: str) -> list[dict]:
        """Scrape active for-sale listings from Zillow.

        Returns empty list on any failure (Cloudflare, timeout, etc).
        """
        try:
            from playwright.async_api import async_playwright
            from playwright_stealth import stealth_async
        except ImportError:
            logger.error("Playwright not installed — skipping Zillow")
            return []

        listings = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                page = await context.new_page()
                await stealth_async(page)

                url = build_search_url(city, state)
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Check for Cloudflare
                content = await page.content()
                if is_cloudflare_challenge(content):
                    logger.warning(f"Zillow Cloudflare challenge detected for {city}, {state}")
                    await browser.close()
                    return []

                # Wait for listing cards
                try:
                    await page.wait_for_selector("[data-test='property-card']", timeout=10000)
                except Exception:
                    logger.warning(f"No Zillow listing cards found for {city}, {state}")
                    await browser.close()
                    return []

                # Extract from current page
                html = await page.content()
                listings.extend(extract_listings_from_html(html))

                await browser.close()

        except Exception as e:
            logger.error(f"Zillow scraper failed for {city}, {state}: {e}")

        return listings


# ── Parsing helpers ─────────────────────────────────────────────────────────

def _parse_price(text: str) -> int | None:
    """Parse price string like '$65,000' to integer."""
    match = re.search(r"\$?([\d,]+)", text)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def _parse_details(card) -> tuple[int | None, int | None, int | None]:
    """Parse beds, baths, sqft from a Zillow property card."""
    beds = baths = sqft = None
    bold_tags = card.find_all("b")
    texts = [b.get_text(strip=True) for b in bold_tags]

    # Typically: ["3", "1", "1,100"] with sibling text "bds", "ba", "sqft"
    for b_tag in bold_tags:
        value_text = b_tag.get_text(strip=True).replace(",", "")
        sibling_text = b_tag.next_sibling
        if sibling_text:
            sibling_str = str(sibling_text).strip().lower()
            if "bd" in sibling_str and value_text.isdigit():
                beds = int(value_text)
            elif "ba" in sibling_str and value_text.isdigit():
                baths = int(value_text)
            elif "sqft" in sibling_str and value_text.isdigit():
                sqft = int(value_text)

    return beds, baths, sqft


def _parse_city(address: str) -> str:
    parts = address.split(",")
    return parts[1].strip() if len(parts) >= 3 else ""


def _parse_state(address: str) -> str:
    parts = address.split(",")
    if len(parts) >= 3:
        state_zip = parts[2].strip()
        return state_zip.split()[0] if state_zip else ""
    return ""


def _parse_zip(address: str) -> str:
    match = re.search(r"\b(\d{5})\b", address)
    return match.group(1) if match else ""
