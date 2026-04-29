"""Tests for the deals router — what-if, ask, sensitivity, and listings endpoints."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(db_path=str(tmp_path / "test.db")))


@pytest.fixture
def market_id(client) -> str:
    resp = client.post("/markets", json={
        "name": "Cleveland OH",
        "city": "Cleveland",
        "state": "OH",
        "zip_codes": ["44101"],
    })
    return resp.json()["id"]


@pytest.fixture
def listing_id(client, market_id) -> str:
    """Create a listing directly in the DB and return its ID."""
    db = client.app.state.db
    return db.upsert_listing({
        "source": "redfin",
        "source_id": "rf-test-1",
        "address": "123 Maple St",
        "normalized_address": "123 maple street",
        "market_id": market_id,
        "zip_code": "44101",
        "price": 65_000,
        "beds": 3,
        "baths": 1.5,
        "sqft": 1100,
    })


# ── GET /listings/{id} ────────────────────────────────────────────────────────

class TestGetListing:
    def test_returns_listing(self, client, listing_id):
        resp = client.get(f"/listings/{listing_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == listing_id
        assert data["address"] == "123 Maple St"

    def test_404_for_missing(self, client):
        resp = client.get("/listings/nonexistent")
        assert resp.status_code == 404


# ── GET /markets/{id}/listings ────────────────────────────────────────────────

class TestListMarketListings:
    def test_returns_listings(self, client, market_id, listing_id):
        resp = client.get(f"/markets/{market_id}/listings")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(l["id"] == listing_id for l in data)

    def test_empty_for_no_listings(self, client, market_id):
        resp = client.get(f"/markets/{market_id}/listings")
        assert resp.status_code == 200
        assert resp.json() == []


# ── POST /deals/{id}/what-if ──────────────────────────────────────────────────

class TestWhatIf:
    def test_recalculates_brrrr_with_overrides(self, client, listing_id):
        resp = client.post(f"/deals/{listing_id}/what-if", json={
            "purchase_price": 60_000,
            "arv": 110_000,
            "estimated_rent": 1500,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "brrrr" in data
        b = data["brrrr"]
        assert b["purchase_price"] == 60_000
        assert b["arv_used"] == 110_000
        assert b["estimated_rent"] == 1500
        assert "grade" in b
        assert "monthly_cashflow" in b

    def test_404_for_missing_listing(self, client):
        resp = client.post("/deals/missing/what-if", json={
            "purchase_price": 60_000, "arv": 100_000, "estimated_rent": 1000,
        })
        assert resp.status_code == 404

    def test_uses_listing_defaults_when_overrides_missing(self, client, listing_id):
        # Update listing with arv + rent so what-if can fall back to them
        db = client.app.state.db
        db.update_analysis(
            listing_id,
            brrrr={"arv_likely": 100_000, "estimated_rent": 1200},
        )
        resp = client.post(f"/deals/{listing_id}/what-if", json={})
        assert resp.status_code == 200
        b = resp.json()["brrrr"]
        # Should pull arv and rent from stored listing
        assert b["arv_used"] == 100_000
        assert b["estimated_rent"] == 1200


# ── POST /deals/{id}/ask ──────────────────────────────────────────────────────

class TestAsk:
    def test_returns_ai_answer(self, client, listing_id):
        with patch("backend.routers.deals.ask_about_deal", return_value="The biggest risk is the roof."):
            resp = client.post(f"/deals/{listing_id}/ask", json={"question": "Biggest risk?"})
        assert resp.status_code == 200
        assert "roof" in resp.json()["answer"]

    def test_400_for_empty_question(self, client, listing_id):
        resp = client.post(f"/deals/{listing_id}/ask", json={"question": "  "})
        assert resp.status_code == 400

    def test_404_for_missing_listing(self, client):
        resp = client.post("/deals/missing/ask", json={"question": "anything"})
        assert resp.status_code == 404


# ── GET /deals/{id}/sensitivity ───────────────────────────────────────────────

class TestSensitivity:
    def test_returns_grid(self, client, listing_id):
        # Need stored ARV/rent so the matrix can build
        db = client.app.state.db
        db.update_analysis(listing_id, brrrr={"arv_likely": 100_000, "estimated_rent": 1300})

        resp = client.get(f"/deals/{listing_id}/sensitivity")
        assert resp.status_code == 200
        data = resp.json()
        assert "prices" in data
        assert "rates" in data
        assert "matrix" in data
        # matrix dims = len(prices) x len(rates)
        assert len(data["matrix"]) == len(data["prices"])
        assert len(data["matrix"][0]) == len(data["rates"])
        # each cell carries coc and grade
        cell = data["matrix"][0][0]
        assert "coc" in cell
        assert "grade" in cell

    def test_404_for_missing_listing(self, client):
        resp = client.get("/deals/missing/sensitivity")
        assert resp.status_code == 404


# ── GET /listings/{id}/comps ──────────────────────────────────────────────────

class TestListingComps:
    def test_returns_comps_list(self, client, listing_id):
        resp = client.get(f"/listings/{listing_id}/comps")
        # 200 with empty list is fine when no comp data cached
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


# ── GET /settings + PUT /settings ─────────────────────────────────────────────

class TestSettings:
    def test_get_returns_defaults(self, client):
        resp = client.get("/settings")
        assert resp.status_code == 200
        data = resp.json()
        # The set the frontend uses
        for key in ("min_price", "max_price", "min_beds", "max_beds", "min_sqft", "max_dom"):
            assert key in data

    def test_put_updates_settings(self, client):
        resp = client.put("/settings", json={"min_price": 30_000, "max_price": 90_000})
        assert resp.status_code == 200
        get_resp = client.get("/settings")
        data = get_resp.json()
        assert data["min_price"] == 30_000
        assert data["max_price"] == 90_000
