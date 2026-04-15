"""Market CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from backend.database import Database
from backend.models import MarketCreate, MarketResponse


def create_markets_router(db: Database) -> APIRouter:
    router = APIRouter(prefix="/markets", tags=["markets"])

    @router.get("", response_model=list[MarketResponse])
    def list_markets():
        return db.list_markets()

    @router.post("", response_model=MarketResponse, status_code=201)
    def create_market(body: MarketCreate):
        market_id = db.create_market(
            name=body.name,
            city=body.city,
            state=body.state,
            zip_codes=body.zip_codes,
        )
        market = db.get_market(market_id)
        return market

    @router.delete("/{market_id}", status_code=204)
    def delete_market(market_id: str):
        existing = db.get_market(market_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Market not found")
        db.delete_market(market_id)
        return Response(status_code=204)

    return router
