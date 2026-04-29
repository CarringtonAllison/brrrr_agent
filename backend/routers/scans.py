"""Scans router — trigger scans and stream SSE events."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.agents.orchestrator import run_scan
from backend.database import Database
from backend.models import ScanStatusResponse


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_scan_background(market: dict, scan_id: str, db: Database) -> None:
    """Placeholder for background scan execution (used by tests to patch).

    In production the stream endpoint drives the scan directly.
    """
    pass


def create_scans_router(db: Database) -> APIRouter:
    router = APIRouter(prefix="/scans", tags=["scans"])

    @router.post("/{market_id}/start", status_code=202)
    def start_scan(market_id: str):
        market = db.get_market(market_id)
        if market is None:
            raise HTTPException(status_code=404, detail="Market not found")

        scan_id = str(uuid.uuid4())
        db.conn.execute(
            "INSERT INTO pipeline_runs (id, market_id, status, started_at) VALUES (?, ?, ?, ?)",
            (scan_id, market_id, "started", _now()),
        )
        db.conn.commit()

        _run_scan_background(market, scan_id, db)

        return {"scan_id": scan_id, "market_id": market_id}

    @router.get("/{market_id}/status", response_model=ScanStatusResponse)
    def scan_status(market_id: str):
        market = db.get_market(market_id)
        if market is None:
            raise HTTPException(status_code=404, detail="Market not found")

        row = db.conn.execute(
            "SELECT id, status, completed_at FROM pipeline_runs WHERE market_id = ? ORDER BY started_at DESC LIMIT 1",
            (market_id,),
        ).fetchone()

        is_active = row is not None and row["status"] in ("started", "running")
        scan_id = row["id"] if row else None

        last_completed_at = None
        last_done = db.conn.execute(
            "SELECT completed_at FROM pipeline_runs WHERE market_id = ? AND completed_at IS NOT NULL ORDER BY completed_at DESC LIMIT 1",
            (market_id,),
        ).fetchone()
        if last_done:
            last_completed_at = last_done["completed_at"]

        return ScanStatusResponse(
            scan_id=scan_id,
            is_active=is_active,
            market_id=market_id,
            last_completed_at=last_completed_at,
        )

    @router.get("/{scan_id}/stream")
    async def stream_scan(scan_id: str):
        row = db.conn.execute(
            "SELECT * FROM pipeline_runs WHERE id = ?", (scan_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Scan not found")

        market_id = row["market_id"]
        market = db.get_market(market_id)

        async def event_generator():
            async for event in run_scan(market):
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "done":
                    db.conn.execute(
                        "UPDATE pipeline_runs SET status = ?, completed_at = ? WHERE id = ?",
                        ("completed", _now(), scan_id),
                    )
                    db.conn.commit()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
