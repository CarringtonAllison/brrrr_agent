"""Application configuration.

Loads sensitive values from environment variables, provides defaults for everything else.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ───────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = os.getenv("DB_PATH", str(PROJECT_ROOT / "brrrr_deals.db"))

# ── API Keys ────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HUD_API_KEY = os.getenv("HUD_API_KEY", "")

# ── Claude Models ───────────────────────────────────────────────────────────

SONNET_MODEL = "claude-sonnet-4-6"
HAIKU_MODEL = "claude-haiku-4-5-20251001"

# ── Email ───────────────────────────────────────────────────────────────────

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "")

# ── Scraper Settings ───────────────────────────────────────────────────────

REDFIN_DELAY_RANGE = (2, 4)
CRAIGSLIST_DELAY_RANGE = (2, 5)
ZILLOW_DELAY_RANGE = (3, 7)
REDFIN_CACHE_HOURS = 6
COMP_CACHE_DAYS = 7
SIMILAR_SOLDS_CACHE_DAYS = 30
RENTAL_CACHE_DAYS = 7
GEOCODE_CACHE_PERMANENT = True

# ── Pre-filter Thresholds ──────────────────────────────────────────────────

MAX_PRICE = 100_000
MIN_PRICE = 25_000
MIN_BEDS = 2
MAX_BEDS = 5
MIN_SQFT = 700
MAX_DOM = 120
ALLOWED_PROPERTY_TYPES = {"single family", "townhouse"}

# ── Cache Freshness ────────────────────────────────────────────────────────

SCAN_CACHE_HOURS = 6
