"""Tests for markets CRUD API endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "test.db"))
    return TestClient(app)


class TestMarketsRouter:
    def test_list_markets_empty(self, client):
        resp = client.get("/markets")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_market(self, client):
        resp = client.post("/markets", json={
            "name": "Cleveland OH",
            "city": "Cleveland",
            "state": "OH",
            "zip_codes": ["44101", "44102"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Cleveland OH"
        assert data["zip_codes"] == ["44101", "44102"]
        assert "id" in data

    def test_create_and_list(self, client):
        client.post("/markets", json={
            "name": "Cleveland OH",
            "city": "Cleveland",
            "state": "OH",
            "zip_codes": ["44101"],
        })
        client.post("/markets", json={
            "name": "Memphis TN",
            "city": "Memphis",
            "state": "TN",
            "zip_codes": ["38109"],
        })
        resp = client.get("/markets")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_delete_market(self, client):
        create_resp = client.post("/markets", json={
            "name": "Cleveland OH",
            "city": "Cleveland",
            "state": "OH",
            "zip_codes": ["44101"],
        })
        market_id = create_resp.json()["id"]

        del_resp = client.delete(f"/markets/{market_id}")
        assert del_resp.status_code == 204

        list_resp = client.get("/markets")
        assert len(list_resp.json()) == 0

    def test_delete_nonexistent_market(self, client):
        resp = client.delete("/markets/nonexistent-id")
        assert resp.status_code == 404


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
