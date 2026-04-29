"""SQLite database module with address normalization and fuzzy matching."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone

from rapidfuzz import fuzz


# ── Address normalization ───────────────────────────────────────────────────

ABBREVIATIONS = {
    r"\bst\b": "street",
    r"\bave\b": "avenue",
    r"\bblvd\b": "boulevard",
    r"\bdr\b": "drive",
    r"\bln\b": "lane",
    r"\bct\b": "court",
    r"\bpl\b": "place",
    r"\brd\b": "road",
    r"\bcir\b": "circle",
    r"\bhwy\b": "highway",
}

UNIT_PATTERN = re.compile(r"\b(apt|unit|suite|ste)\s*\S+|#\s*\S+", re.IGNORECASE)


def normalize_address(address: str) -> str:
    """Normalize an address for deduplication.

    Lowercase, strip punctuation, expand abbreviations, strip unit numbers,
    collapse whitespace.
    """
    addr = address.strip().lower()

    # Strip unit/apt numbers (before punctuation removal so # is intact)
    addr = UNIT_PATTERN.sub("", addr)

    # Strip periods (but keep commas for city separation)
    addr = addr.replace(".", "")

    # Expand abbreviations (word-boundary matching)
    for pattern, replacement in ABBREVIATIONS.items():
        addr = re.sub(pattern, replacement, addr)

    # Collapse multiple spaces
    addr = re.sub(r"\s+", " ", addr).strip()

    return addr


def fuzzy_match(addr1: str, addr2: str, threshold: int = 88) -> bool:
    """Check if two normalized addresses are similar enough to be the same property."""
    return fuzz.ratio(addr1, addr2) >= threshold


# ── Database class ──────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS markets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    zip_codes TEXT NOT NULL,  -- JSON array
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    address TEXT NOT NULL,
    normalized_address TEXT NOT NULL,
    market_id TEXT NOT NULL,
    zip_code TEXT,
    price REAL,
    previous_price REAL,
    beds INTEGER,
    baths REAL,
    sqft INTEGER,
    year_built INTEGER,
    property_type TEXT,
    description TEXT,
    listing_url TEXT,
    photos TEXT,              -- JSON array
    days_on_market INTEGER,
    latitude REAL,
    longitude REAL,
    first_seen_at TEXT,
    last_seen_at TEXT,
    price_changed_at TEXT,
    -- Analysis results (nullable, filled later)
    arv_conservative REAL,
    arv_likely REAL,
    arv_aggressive REAL,
    total_all_in REAL,
    cash_left_in_deal REAL,
    estimated_rent REAL,
    monthly_cashflow REAL,
    coc_return REAL,
    dscr REAL,
    rent_to_price REAL,
    grade TEXT,
    ai_summary TEXT,
    ai_review TEXT,           -- JSON blob
    motivation_score INTEGER,
    negotiation_advice TEXT,  -- JSON blob
    UNIQUE(source, source_id)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id TEXT PRIMARY KEY,
    market_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'started',
    phase_completed INTEGER DEFAULT 0,
    batch_id_sonnet TEXT,
    batch_id_haiku TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS comp_cache (
    cache_key TEXT PRIMARY KEY,
    comps_json TEXT NOT NULL,
    source TEXT NOT NULL,
    cached_at TEXT NOT NULL,
    comp_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rental_comps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zip_code TEXT NOT NULL,
    beds INTEGER NOT NULL,
    median_rent REAL,
    sample_size INTEGER,
    fetched_at TEXT NOT NULL,
    UNIQUE(zip_code, beds)
);

CREATE TABLE IF NOT EXISTS geocode_cache (
    normalized_address TEXT PRIMARY KEY,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    source TEXT NOT NULL,
    geocoded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scraper_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    source TEXT NOT NULL,
    market_id TEXT NOT NULL,
    listings_found INTEGER DEFAULT 0,
    errors TEXT,
    timestamp TEXT NOT NULL
);
"""


class Database:
    """SQLite database with WAL mode for the BRRRR deal finder."""

    def __init__(self, db_path: str = "brrrr_deals.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def get_table_names(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return [row["name"] for row in rows]

    # ── Markets ─────────────────────────────────────────────────────────────

    def create_market(
        self, name: str, city: str, state: str, zip_codes: list[str]
    ) -> str:
        market_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO markets (id, name, city, state, zip_codes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (market_id, name, city, state, json.dumps(zip_codes), _now()),
        )
        self.conn.commit()
        return market_id

    def get_market(self, market_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM markets WHERE id = ?", (market_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row, json_fields=["zip_codes"])

    def list_markets(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM markets ORDER BY created_at").fetchall()
        return [_row_to_dict(r, json_fields=["zip_codes"]) for r in rows]

    def delete_market(self, market_id: str) -> None:
        self.conn.execute("DELETE FROM markets WHERE id = ?", (market_id,))
        self.conn.commit()

    # ── Listings ────────────────────────────────────────────────────────────

    def upsert_listing(self, data: dict) -> str:
        """Insert or update a listing. Returns the listing ID.

        On conflict (same source + source_id), updates price and tracks previous.
        """
        existing = self.conn.execute(
            "SELECT id, price FROM listings WHERE source = ? AND source_id = ?",
            (data["source"], data["source_id"]),
        ).fetchone()

        now = _now()

        if existing:
            listing_id = existing["id"]
            old_price = existing["price"]
            new_price = data.get("price")

            updates = {"last_seen_at": now}
            if new_price is not None and new_price != old_price:
                updates["previous_price"] = old_price
                updates["price"] = new_price
                updates["price_changed_at"] = now

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [listing_id]
            self.conn.execute(
                f"UPDATE listings SET {set_clause} WHERE id = ?", values
            )
            self.conn.commit()
            return listing_id

        listing_id = str(uuid.uuid4())
        self.conn.execute(
            """INSERT INTO listings (
                id, source, source_id, address, normalized_address,
                market_id, zip_code, price, beds, baths, sqft,
                first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                listing_id,
                data["source"],
                data["source_id"],
                data.get("address", ""),
                data.get("normalized_address", ""),
                data.get("market_id", ""),
                data.get("zip_code", ""),
                data.get("price"),
                data.get("beds"),
                data.get("baths"),
                data.get("sqft"),
                now,
                now,
            ),
        )
        self.conn.commit()
        return listing_id

    def get_listing(self, listing_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)

    def list_listings_for_market(self, market_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM listings WHERE market_id = ? ORDER BY last_seen_at DESC",
            (market_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def update_analysis(
        self,
        listing_id: str,
        brrrr: dict | None = None,
        grade: str | None = None,
        ai_review: dict | None = None,
        ai_summary: str | None = None,
        motivation_score: int | None = None,
        negotiation_advice: dict | None = None,
    ) -> None:
        """Persist analysis results to a listing. Only updates fields that are not None."""
        updates: dict[str, object] = {}

        if brrrr is not None:
            for src, col in [
                ("cash_left_in_deal", "cash_left_in_deal"),
                ("monthly_cashflow", "monthly_cashflow"),
                ("coc_return", "coc_return"),
                ("dscr", "dscr"),
                ("rent_to_price", "rent_to_price"),
                ("total_all_in", "total_all_in"),
                ("estimated_rent", "estimated_rent"),
                ("arv_likely", "arv_likely"),
                ("arv_conservative", "arv_conservative"),
                ("arv_aggressive", "arv_aggressive"),
            ]:
                if src in brrrr and brrrr[src] is not None:
                    updates[col] = brrrr[src]

        if grade is not None:
            updates["grade"] = grade
        if ai_review is not None:
            updates["ai_review"] = json.dumps(ai_review)
        if ai_summary is not None:
            updates["ai_summary"] = ai_summary
        if motivation_score is not None:
            updates["motivation_score"] = motivation_score
        if negotiation_advice is not None:
            updates["negotiation_advice"] = json.dumps(negotiation_advice)

        if not updates:
            return

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [listing_id]
        self.conn.execute(
            f"UPDATE listings SET {set_clause} WHERE id = ?", values
        )
        self.conn.commit()


# ── Helpers ─────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row, json_fields: list[str] | None = None) -> dict:
    d = dict(row)
    if json_fields:
        for field in json_fields:
            if field in d and isinstance(d[field], str):
                d[field] = json.loads(d[field])
    return d
