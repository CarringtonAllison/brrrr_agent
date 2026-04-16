"""Tests for the scans API — trigger endpoint and SSE stream."""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "test.db"))
    return TestClient(app)


@pytest.fixture
def market_id(client) -> str:
    resp = client.post("/markets", json={
        "name": "Cleveland OH",
        "city": "Cleveland",
        "state": "OH",
        "zip_codes": ["44101", "44102"],
    })
    assert resp.status_code == 201
    return resp.json()["id"]


# ── POST /scans/{market_id}/start ─────────────────────────────────────────────

class TestStartScan:
    def test_start_scan_returns_scan_id(self, client, market_id):
        resp = client.post(f"/scans/{market_id}/start")
        assert resp.status_code == 202
        data = resp.json()
        assert "scan_id" in data
        assert data["market_id"] == market_id

    def test_start_scan_nonexistent_market(self, client):
        resp = client.post("/scans/nonexistent-id/start")
        assert resp.status_code == 404

    def test_start_scan_creates_pipeline_run(self, client, market_id):
        resp = client.post(f"/scans/{market_id}/start")
        assert resp.status_code == 202
        scan_id = resp.json()["scan_id"]
        assert scan_id is not None
        assert len(scan_id) > 0


# ── GET /scans/{market_id}/status ─────────────────────────────────────────────

class TestScanStatus:
    def test_status_before_scan(self, client, market_id):
        resp = client.get(f"/scans/{market_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["market_id"] == market_id
        assert data["is_active"] is False

    def test_status_nonexistent_market(self, client):
        resp = client.get("/scans/nonexistent-id/status")
        assert resp.status_code == 404


# ── GET /scans/{scan_id}/stream ───────────────────────────────────────────────

class TestScanStream:
    def test_stream_nonexistent_scan(self, client):
        resp = client.get("/scans/nonexistent-scan/stream")
        assert resp.status_code == 404

    def test_stream_returns_sse_content_type(self, client, market_id):
        """Start a scan and immediately stream — should be SSE."""
        with patch("backend.routers.scans._run_scan_background") as mock_bg:
            mock_bg.return_value = None
            start_resp = client.post(f"/scans/{market_id}/start")
            scan_id = start_resp.json()["scan_id"]

        # Stream with mock orchestrator that returns immediate done event
        async def mock_gen(*args, **kwargs):
            yield {"type": "done", "summary": {"total": 0, "strong": 0, "good": 0}}

        with patch("backend.routers.scans.run_scan", mock_gen):
            resp = client.get(f"/scans/{scan_id}/stream")
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_stream_emits_done_event(self, client, market_id):
        """Stream should emit a 'done' SSE event."""
        start_resp = client.post(f"/scans/{market_id}/start")
        scan_id = start_resp.json()["scan_id"]

        async def mock_gen(*args, **kwargs):
            yield {"type": "source_status", "source": "redfin", "status": "scraping", "count": 0}
            yield {"type": "done", "summary": {"total": 0, "strong": 0, "good": 0}}

        with patch("backend.routers.scans.run_scan", mock_gen):
            resp = client.get(f"/scans/{scan_id}/stream")

        assert resp.status_code == 200
        body = resp.text
        assert "done" in body

    def test_stream_emits_valid_sse_format(self, client, market_id):
        """Each SSE event should be prefixed with 'data: '."""
        start_resp = client.post(f"/scans/{market_id}/start")
        scan_id = start_resp.json()["scan_id"]

        async def mock_gen(*args, **kwargs):
            yield {"type": "done", "summary": {"total": 0, "strong": 0, "good": 0}}

        with patch("backend.routers.scans.run_scan", mock_gen):
            resp = client.get(f"/scans/{scan_id}/stream")

        assert "data:" in resp.text
