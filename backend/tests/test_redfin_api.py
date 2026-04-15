"""Tests for Redfin API scraper — response parsing, data extraction, caching."""

import json
import pytest
from unittest.mock import patch, MagicMock

from backend.scrapers.redfin_api import (
    parse_redfin_response,
    extract_listings_from_gis,
    extract_sold_comps_from_gis,
    build_gis_url,
    build_similar_solds_url,
    RedfinScraper,
)


# ── Sample Redfin GIS response (simplified) ────────────────────────────────

SAMPLE_GIS_RESPONSE = """{}&&{
  "payload": {
    "homes": [
      {
        "homeData": {
          "propertyId": 12345,
          "listingId": 67890,
          "addressInfo": {
            "formattedStreetLine": "123 Main St",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44108",
            "centroid": {"centroid": {"longitude": -81.63, "latitude": 41.50}}
          },
          "priceInfo": {"amount": 65000},
          "bedrooms": 3,
          "bathrooms": 1,
          "sqFt": {"value": 1100},
          "yearBuilt": {"yearBuilt": 1952},
          "listingType": "SF",
          "daysOnMarket": {"daysOnMarket": 45},
          "url": "/OH/Cleveland/123-Main-St-44108/home/12345"
        }
      },
      {
        "homeData": {
          "propertyId": 22222,
          "listingId": 33333,
          "addressInfo": {
            "formattedStreetLine": "456 Oak Ave",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44108",
            "centroid": {"centroid": {"longitude": -81.64, "latitude": 41.51}}
          },
          "priceInfo": {"amount": 78000},
          "bedrooms": 3,
          "bathrooms": 2,
          "sqFt": {"value": 1400},
          "yearBuilt": {"yearBuilt": 1965},
          "listingType": "SF",
          "daysOnMarket": {"daysOnMarket": 12},
          "url": "/OH/Cleveland/456-Oak-Ave-44108/home/22222"
        }
      }
    ]
  }
}"""

SAMPLE_SOLD_RESPONSE = """{}&&{
  "payload": {
    "homes": [
      {
        "homeData": {
          "propertyId": 99999,
          "addressInfo": {
            "formattedStreetLine": "789 Elm Dr",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44108",
            "centroid": {"centroid": {"longitude": -81.65, "latitude": 41.49}}
          },
          "priceInfo": {"amount": 112000},
          "bedrooms": 3,
          "bathrooms": 1.5,
          "sqFt": {"value": 1200},
          "yearBuilt": {"yearBuilt": 1958},
          "listingType": "SF",
          "soldDate": "2026-02-15T00:00:00Z",
          "url": "/OH/Cleveland/789-Elm-Dr-44108/home/99999"
        }
      }
    ]
  }
}"""


class TestParseRedfinResponse:
    def test_strips_prefix(self):
        """Redfin wraps JSON with {}&&, must strip before parsing."""
        data = parse_redfin_response(SAMPLE_GIS_RESPONSE)
        assert "payload" in data

    def test_handles_clean_json(self):
        """If response has no prefix, should still parse."""
        clean = '{"payload": {"homes": []}}'
        data = parse_redfin_response(clean)
        assert data["payload"]["homes"] == []

    def test_raises_on_invalid(self):
        with pytest.raises(ValueError):
            parse_redfin_response("totally invalid")


class TestExtractListings:
    def test_extracts_two_listings(self):
        data = parse_redfin_response(SAMPLE_GIS_RESPONSE)
        listings = extract_listings_from_gis(data)
        assert len(listings) == 2

    def test_listing_fields(self):
        data = parse_redfin_response(SAMPLE_GIS_RESPONSE)
        listings = extract_listings_from_gis(data)
        first = listings[0]
        assert first["source"] == "redfin"
        assert first["source_id"] == "12345"
        assert first["address"] == "123 Main St"
        assert first["city"] == "Cleveland"
        assert first["state"] == "OH"
        assert first["zip_code"] == "44108"
        assert first["price"] == 65_000
        assert first["beds"] == 3
        assert first["baths"] == 1
        assert first["sqft"] == 1100
        assert first["year_built"] == 1952
        assert first["days_on_market"] == 45
        assert first["latitude"] == pytest.approx(41.50)
        assert first["longitude"] == pytest.approx(-81.63)
        assert "redfin.com" in first["listing_url"]


class TestExtractSoldComps:
    def test_extracts_sold_comp(self):
        data = parse_redfin_response(SAMPLE_SOLD_RESPONSE)
        comps = extract_sold_comps_from_gis(data)
        assert len(comps) == 1
        comp = comps[0]
        assert comp["sale_price"] == 112_000
        assert comp["address"] == "789 Elm Dr"
        assert comp["beds"] == 3
        assert comp["sqft"] == 1200


class TestBuildUrls:
    def test_gis_active_url(self):
        url = build_gis_url(region_id="19013", region_type="6", status="active")
        assert "region_id=19013" in url
        assert "status=1" in url

    def test_gis_sold_url(self):
        url = build_gis_url(region_id="19013", region_type="6", status="sold", sold_days=730)
        assert "status=9" in url
        assert "sold_within_days=730" in url

    def test_similar_solds_url(self):
        url = build_similar_solds_url(property_id=12345, listing_id=67890)
        assert "propertyId=12345" in url
        assert "listingId=67890" in url


class TestRedfinScraper:
    @patch("backend.scrapers.redfin_api.requests.get")
    def test_scrape_active_listings(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_GIS_RESPONSE
        mock_get.return_value = mock_resp

        scraper = RedfinScraper()
        market = {
            "redfin_region_id": "19013",
            "redfin_region_type": "6",
            "zip_codes": ["44108"],
        }
        listings = scraper.get_active_listings(market)
        assert len(listings) == 2
        assert listings[0]["source"] == "redfin"

    @patch("backend.scrapers.redfin_api.requests.get")
    def test_handles_429_gracefully(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp

        scraper = RedfinScraper(max_retries=1, backoff_base=0.01)
        market = {
            "redfin_region_id": "19013",
            "redfin_region_type": "6",
            "zip_codes": ["44108"],
        }
        listings = scraper.get_active_listings(market)
        assert listings == []

    @patch("backend.scrapers.redfin_api.requests.get")
    def test_handles_error_gracefully(self, mock_get):
        mock_get.side_effect = Exception("Network error")

        scraper = RedfinScraper(max_retries=1, backoff_base=0.01)
        market = {
            "redfin_region_id": "19013",
            "redfin_region_type": "6",
            "zip_codes": ["44108"],
        }
        listings = scraper.get_active_listings(market)
        assert listings == []
