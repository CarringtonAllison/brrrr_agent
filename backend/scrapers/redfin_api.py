"""Redfin API scraper — active listings, sold comps, and similar solds.

Uses Redfin's internal stingray API endpoints. No API key needed.
Response JSON is prefixed with {}&&  which must be stripped before parsing.
"""

from __future__ import annotations

import json
import logging
import random
import time
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://www.redfin.com/stingray/api"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.redfin.com/",
}


def parse_redfin_response(text: str) -> dict:
    """Strip the {}&&  prefix from Redfin's JSON response and parse it.

    Raises ValueError if the response cannot be parsed.
    """
    cleaned = text.strip()

    # Strip the {}&&  prefix if present
    if cleaned.startswith("{}&&"):
        cleaned = cleaned[4:]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Redfin response: {e}") from e


def extract_listings_from_gis(data: dict) -> list[dict]:
    """Extract standardized listing dicts from a Redfin GIS response."""
    homes = data.get("payload", {}).get("homes", [])
    listings = []

    for home in homes:
        hd = home.get("homeData", {})
        addr_info = hd.get("addressInfo", {})
        centroid = addr_info.get("centroid", {}).get("centroid", {})

        listing = {
            "source": "redfin",
            "source_id": str(hd.get("propertyId", "")),
            "property_id": hd.get("propertyId"),
            "listing_id": hd.get("listingId"),
            "address": addr_info.get("formattedStreetLine", ""),
            "city": addr_info.get("city", ""),
            "state": addr_info.get("state", ""),
            "zip_code": addr_info.get("zip", ""),
            "price": hd.get("priceInfo", {}).get("amount"),
            "beds": hd.get("bedrooms"),
            "baths": hd.get("bathrooms"),
            "sqft": hd.get("sqFt", {}).get("value"),
            "year_built": hd.get("yearBuilt", {}).get("yearBuilt"),
            "property_type": _map_listing_type(hd.get("listingType", "")),
            "days_on_market": hd.get("daysOnMarket", {}).get("daysOnMarket"),
            "latitude": centroid.get("latitude"),
            "longitude": centroid.get("longitude"),
            "listing_url": f"https://www.redfin.com{hd.get('url', '')}",
        }
        listings.append(listing)

    return listings


def extract_sold_comps_from_gis(data: dict) -> list[dict]:
    """Extract sold comp data from a Redfin GIS response (status=9)."""
    homes = data.get("payload", {}).get("homes", [])
    comps = []

    for home in homes:
        hd = home.get("homeData", {})
        addr_info = hd.get("addressInfo", {})
        centroid = addr_info.get("centroid", {}).get("centroid", {})

        comp = {
            "source": "redfin_gis",
            "address": addr_info.get("formattedStreetLine", ""),
            "city": addr_info.get("city", ""),
            "state": addr_info.get("state", ""),
            "zip_code": addr_info.get("zip", ""),
            "sale_price": hd.get("priceInfo", {}).get("amount"),
            "sale_date": hd.get("soldDate"),
            "beds": hd.get("bedrooms"),
            "baths": hd.get("bathrooms"),
            "sqft": hd.get("sqFt", {}).get("value"),
            "year_built": hd.get("yearBuilt", {}).get("yearBuilt"),
            "latitude": centroid.get("latitude"),
            "longitude": centroid.get("longitude"),
        }
        comps.append(comp)

    return comps


def build_gis_url(
    region_id: str,
    region_type: str,
    status: str = "active",
    sold_days: int = 730,
    num_homes: int = 350,
) -> str:
    """Build a Redfin GIS API URL for active or sold listings."""
    params = {
        "al": "1",
        "region_id": region_id,
        "region_type": region_type,
        "uipt": "1,2",  # single family + townhouse
        "num_homes": str(num_homes),
        "v": "8",
    }

    if status == "sold":
        params["status"] = "9"
        params["sold_within_days"] = str(sold_days)
    else:
        params["status"] = "1"

    return f"{BASE_URL}/gis?{urlencode(params)}"


def build_similar_solds_url(property_id: int, listing_id: int) -> str:
    """Build URL for Redfin's similar solds endpoint."""
    params = {
        "propertyId": str(property_id),
        "listingId": str(listing_id),
        "accessLevel": "3",
        "pageType": "3",
    }
    return f"{BASE_URL}/home/details/similars/solds?{urlencode(params)}"


class RedfinScraper:
    """Scrapes listings and comps from Redfin's internal API."""

    def __init__(
        self,
        max_retries: int = 3,
        backoff_base: float = 5.0,
        delay_range: tuple[float, float] = (2, 4),
    ):
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.delay_range = delay_range
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_active_listings(self, market: dict) -> list[dict]:
        """Fetch active for-sale listings for a market."""
        url = build_gis_url(
            region_id=market["redfin_region_id"],
            region_type=market["redfin_region_type"],
        )
        text = self._fetch_with_retry(url)
        if text is None:
            return []

        try:
            data = parse_redfin_response(text)
            return extract_listings_from_gis(data)
        except ValueError:
            logger.error("Failed to parse Redfin active listings response")
            return []

    def get_sold_comps(
        self, region_id: str, region_type: str, sold_days: int = 730
    ) -> list[dict]:
        """Fetch sold comps for a region."""
        url = build_gis_url(
            region_id=region_id,
            region_type=region_type,
            status="sold",
            sold_days=sold_days,
            num_homes=100,
        )
        text = self._fetch_with_retry(url)
        if text is None:
            return []

        try:
            data = parse_redfin_response(text)
            return extract_sold_comps_from_gis(data)
        except ValueError:
            logger.error("Failed to parse Redfin sold comps response")
            return []

    def get_similar_solds(
        self, property_id: int, listing_id: int
    ) -> list[dict]:
        """Fetch Redfin's curated similar sold properties for a listing."""
        url = build_similar_solds_url(property_id, listing_id)
        text = self._fetch_with_retry(url)
        if text is None:
            return []

        try:
            data = parse_redfin_response(text)
            # Similar solds response structure differs from GIS
            homes = data.get("payload", {}).get("homes", [])
            comps = []
            for home in homes:
                hd = home.get("homeData", {})
                addr_info = hd.get("addressInfo", {})
                comps.append({
                    "source": "redfin_similars",
                    "address": addr_info.get("formattedStreetLine", ""),
                    "zip_code": addr_info.get("zip", ""),
                    "sale_price": hd.get("priceInfo", {}).get("amount"),
                    "sale_date": hd.get("soldDate"),
                    "beds": hd.get("bedrooms"),
                    "baths": hd.get("bathrooms"),
                    "sqft": hd.get("sqFt", {}).get("value"),
                })
            return comps
        except (ValueError, KeyError):
            logger.error("Failed to parse Redfin similar solds response")
            return []

    def _fetch_with_retry(self, url: str) -> str | None:
        """Fetch a URL with exponential backoff on 429s."""
        for attempt in range(self.max_retries):
            try:
                time.sleep(random.uniform(*self.delay_range))
                resp = self.session.get(url, timeout=15)

                if resp.status_code == 200:
                    return resp.text
                elif resp.status_code == 429:
                    wait = self.backoff_base * (2 ** attempt)
                    logger.warning(
                        f"Redfin 429, backing off {wait:.0f}s (attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait)
                else:
                    logger.warning(f"Redfin returned status {resp.status_code}")
                    return None

            except Exception as e:
                logger.error(f"Redfin request failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.backoff_base)
                else:
                    return None

        return None


def _map_listing_type(redfin_type: str) -> str:
    """Map Redfin listing type codes to standardized names."""
    mapping = {
        "SF": "single family",
        "CN": "condo",
        "TH": "townhouse",
        "MF": "multi-family",
        "LN": "land",
    }
    return mapping.get(redfin_type, redfin_type.lower())
