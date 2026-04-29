"""Tests for database module — address normalization and core operations."""

import pytest

from backend.database import normalize_address, fuzzy_match, Database


class TestNormalizeAddress:
    def test_lowercase(self):
        assert normalize_address("123 MAIN ST") == "123 main street"

    def test_expand_st(self):
        assert normalize_address("123 Main St") == "123 main street"

    def test_expand_ave(self):
        assert normalize_address("456 Oak Ave") == "456 oak avenue"

    def test_expand_blvd(self):
        assert normalize_address("789 Elm Blvd") == "789 elm boulevard"

    def test_expand_dr(self):
        assert normalize_address("100 Pine Dr") == "100 pine drive"

    def test_expand_ln(self):
        assert normalize_address("55 Maple Ln") == "55 maple lane"

    def test_expand_ct(self):
        assert normalize_address("12 Cedar Ct") == "12 cedar court"

    def test_expand_rd(self):
        assert normalize_address("300 Park Rd") == "300 park road"

    def test_strip_apt_number(self):
        assert normalize_address("123 Main St Apt 4B") == "123 main street"

    def test_strip_unit_number(self):
        assert normalize_address("123 Main St Unit 12") == "123 main street"

    def test_strip_hash_number(self):
        assert normalize_address("123 Main St #3") == "123 main street"

    def test_collapse_whitespace(self):
        assert normalize_address("123  Main   St") == "123 main street"

    def test_strip_leading_trailing(self):
        assert normalize_address("  123 Main St  ") == "123 main street"

    def test_strip_punctuation(self):
        assert normalize_address("123 Main St., Cleveland") == "123 main street, cleveland"


class TestFuzzyMatch:
    def test_exact_match(self):
        assert fuzzy_match("123 main street", "123 main street") is True

    def test_close_match(self):
        """After normalization, 'st' becomes 'street' — both should match."""
        a = normalize_address("123 Main St")
        b = normalize_address("123 Main Street")
        assert fuzzy_match(a, b) is True

    def test_no_match(self):
        assert fuzzy_match("123 main street", "456 oak avenue") is False

    def test_threshold(self):
        """Addresses with minor differences should match at 88%."""
        assert fuzzy_match("123 main street cleveland", "123 main street clevland") is True


class TestDatabase:
    @pytest.fixture
    def db(self, tmp_path):
        """Create a fresh test database."""
        db_path = str(tmp_path / "test.db")
        return Database(db_path)

    def test_create_tables(self, db):
        """Tables should be created on init."""
        tables = db.get_table_names()
        assert "markets" in tables
        assert "listings" in tables
        assert "pipeline_runs" in tables

    def test_market_crud(self, db):
        market_id = db.create_market("Cleveland OH", "Cleveland", "OH", ["44101", "44102"])
        assert market_id is not None

        market = db.get_market(market_id)
        assert market["name"] == "Cleveland OH"
        assert market["zip_codes"] == ["44101", "44102"]

        markets = db.list_markets()
        assert len(markets) == 1

        db.delete_market(market_id)
        assert db.get_market(market_id) is None

    def test_upsert_listing(self, db):
        """Insert a listing, then upsert with new price."""
        market_id = db.create_market("Test", "Test", "OH", ["44101"])
        listing_data = {
            "source": "redfin",
            "source_id": "rf_123",
            "address": "123 Main St",
            "normalized_address": "123 main street",
            "market_id": market_id,
            "zip_code": "44101",
            "price": 75_000,
            "beds": 3,
            "baths": 1.5,
            "sqft": 1100,
        }
        listing_id = db.upsert_listing(listing_data)
        assert listing_id is not None

        # Upsert same listing with new price
        listing_data["price"] = 70_000
        listing_id_2 = db.upsert_listing(listing_data)
        assert listing_id_2 == listing_id  # same listing

        listing = db.get_listing(listing_id)
        assert listing["price"] == 70_000
        assert listing["previous_price"] == 75_000


class TestUpdateAnalysis:
    def test_persists_brrrr_and_ai_fields(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        market_id = db.create_market("Test", "Test", "OH", ["44101"])
        listing_id = db.upsert_listing({
            "source": "redfin",
            "source_id": "rf_xyz",
            "address": "9 Pine Way",
            "normalized_address": "9 pine way",
            "market_id": market_id,
            "zip_code": "44101",
            "price": 68_000,
            "beds": 3,
            "baths": 1.0,
            "sqft": 1100,
        })

        db.update_analysis(
            listing_id,
            brrrr={"grade": "GOOD", "cash_left_in_deal": 8000, "monthly_cashflow": 200,
                   "coc_return": 0.13, "dscr": 1.25, "rent_to_price": 0.014,
                   "total_all_in": 95000, "estimated_rent": 950,
                   "arv_likely": 95000},
            grade="GOOD",
            ai_review={"verdict": "GOOD", "summary": "solid", "confidence": 0.7},
            ai_summary="Solid BRRRR. Watch the roof.",
            motivation_score=6,
            negotiation_advice={"offer_range_low": 55000, "offer_range_high": 62000,
                                "max_purchase_breakeven": 65000, "was_clamped": False},
        )

        listing = db.get_listing(listing_id)
        assert listing["grade"] == "GOOD"
        assert listing["cash_left_in_deal"] == 8000
        assert listing["coc_return"] == 0.13
        assert listing["motivation_score"] == 6
        # JSON blobs round-trip
        import json as _json
        assert _json.loads(listing["ai_review"])["verdict"] == "GOOD"
        assert _json.loads(listing["negotiation_advice"])["offer_range_low"] == 55000

    def test_partial_update_leaves_other_fields_alone(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        market_id = db.create_market("Test", "Test", "OH", ["44101"])
        listing_id = db.upsert_listing({
            "source": "redfin", "source_id": "x", "address": "1 A St",
            "normalized_address": "1 a street", "market_id": market_id,
            "zip_code": "44101", "price": 50_000, "beds": 3, "baths": 1.0, "sqft": 900,
        })

        db.update_analysis(listing_id, grade="MAYBE", motivation_score=4)
        listing = db.get_listing(listing_id)
        assert listing["grade"] == "MAYBE"
        assert listing["motivation_score"] == 4
        # untouched fields stay None
        assert listing["ai_review"] is None
