"""Geocoding module — address to coordinates, ZIP proximity, bounding box math.

Uses free data sources only:
- pgeocode (offline) for ZIP code centroids
- US Census Bureau geocoder (free, no API key) for street addresses
"""

from __future__ import annotations

import math
import time

import httpx
import pgeocode
from geopy.distance import geodesic

# Initialize pgeocode once (downloads data on first use, then offline)
_nomi = pgeocode.Nominatim("us")


def bounding_box_from_center(
    lat: float, lon: float, radius_miles: float
) -> tuple[float, float, float, float]:
    """Compute a bounding box for a center point and radius.

    Returns (south_lat, north_lat, west_lon, east_lon).
    """
    if radius_miles <= 0:
        return (lat, lat, lon, lon)

    lat_delta = radius_miles / 69.0
    lon_delta = radius_miles / (69.0 * math.cos(math.radians(lat)))

    return (
        lat - lat_delta,
        lat + lat_delta,
        lon - lon_delta,
        lon + lon_delta,
    )


def get_zip_centroid(zip_code: str) -> tuple[float, float] | None:
    """Look up the centroid coordinates for a US ZIP code via pgeocode (offline).

    Returns (lat, lon) or None if the ZIP is not found.
    """
    result = _nomi.query_postal_code(zip_code)
    if result is None or math.isnan(result.latitude) or math.isnan(result.longitude):
        return None
    return (float(result.latitude), float(result.longitude))


def find_nearby_zips(
    center_lat: float, center_lon: float, radius_miles: float = 5.0
) -> list[dict]:
    """Find all ZIP codes whose centroids fall within radius of a center point.

    Returns list of {"zip": str, "distance_miles": float} sorted by distance.
    """
    bbox = bounding_box_from_center(center_lat, center_lon, radius_miles)
    df = _nomi._data

    # Fast rectangular filter
    candidates = df[
        (df["latitude"] >= bbox[0])
        & (df["latitude"] <= bbox[1])
        & (df["longitude"] >= bbox[2])
        & (df["longitude"] <= bbox[3])
    ]

    center = (center_lat, center_lon)
    nearby = []
    for _, row in candidates.iterrows():
        if math.isnan(row["latitude"]) or math.isnan(row["longitude"]):
            continue
        dist = geodesic(center, (row["latitude"], row["longitude"])).miles
        if dist <= radius_miles:
            nearby.append({
                "zip": str(row["postal_code"]),
                "distance_miles": round(dist, 2),
            })

    return sorted(nearby, key=lambda x: x["distance_miles"])


def geocode_address(
    address: str,
    cache: dict | None = None,
) -> tuple[float, float] | None:
    """Geocode a street address to (lat, lon).

    Uses Census Bureau geocoder (free). Results are cached in the provided dict
    if given, or callers can use the DB cache externally.
    """
    key = address.strip().lower()

    if cache is not None and key in cache:
        return cache[key]

    result = _census_geocode(address)

    if result is not None and cache is not None:
        cache[key] = result

    return result


def _census_geocode(address: str) -> tuple[float, float] | None:
    """Call the US Census Bureau geocoder API.

    Free, no API key required. Rate: ~2 requests/sec is safe.
    """
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "format": "json",
    }

    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        if resp.status_code != 200:
            return None

        data = resp.json()
        matches = data.get("result", {}).get("addressMatches", [])
        if not matches:
            return None

        coords = matches[0]["coordinates"]
        return (float(coords["y"]), float(coords["x"]))

    except (httpx.HTTPError, KeyError, ValueError, IndexError):
        return None
