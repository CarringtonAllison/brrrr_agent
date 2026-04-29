"""Deals + listings + settings endpoints.

- GET    /listings/{id}                      single listing
- GET    /listings/{id}/comps                cached comps for a listing
- GET    /markets/{id}/listings              all listings for a market
- POST   /deals/{id}/what-if                 re-run BRRRR with overrides
- POST   /deals/{id}/ask                     free-form Q&A via Sonnet
- GET    /deals/{id}/sensitivity             price x interest-rate CoC matrix
- GET    /settings                           current pre-filter thresholds
- PUT    /settings                           update pre-filter thresholds
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agents.deal_analyst import ask_about_deal
from backend.brrrr_calculator import (
    calculate_cashflow,
    calculate_coc_return,
    calculate_dscr,
    calculate_monthly_mortgage,
    grade_deal,
    run_full_analysis,
)
from backend.config import ANTHROPIC_API_KEY
from backend.database import Database


SETTINGS_KEYS = ("min_price", "max_price", "min_beds", "max_beds", "min_sqft", "max_dom")


# ── Request/response models ──────────────────────────────────────────────────

class WhatIfRequest(BaseModel):
    purchase_price: float | None = None
    rehab_cost: float | None = None
    arv: float | None = None
    estimated_rent: float | None = None


class AskRequest(BaseModel):
    question: str


class SettingsUpdate(BaseModel):
    min_price: float | None = None
    max_price: float | None = None
    min_beds: int | None = None
    max_beds: int | None = None
    min_sqft: int | None = None
    max_dom: int | None = None


# ── In-process settings store ────────────────────────────────────────────────
# Mutable so PUT /settings reflects in subsequent GETs within a process.

def _default_settings() -> dict[str, Any]:
    from backend import config
    return {
        "min_price": config.MIN_PRICE,
        "max_price": config.MAX_PRICE,
        "min_beds": config.MIN_BEDS,
        "max_beds": config.MAX_BEDS,
        "min_sqft": config.MIN_SQFT,
        "max_dom": config.MAX_DOM,
    }


def create_deals_router(db: Database) -> APIRouter:
    router = APIRouter(tags=["deals"])
    settings_state: dict[str, Any] = _default_settings()

    # ── /listings/{id} ────────────────────────────────────────────────────────

    @router.get("/listings/{listing_id}")
    def get_listing(listing_id: str):
        listing = db.get_listing(listing_id)
        if listing is None:
            raise HTTPException(status_code=404, detail="Listing not found")
        return _hydrate_listing(listing)

    @router.get("/listings/{listing_id}/comps")
    def get_listing_comps(listing_id: str):
        listing = db.get_listing(listing_id)
        if listing is None:
            raise HTTPException(status_code=404, detail="Listing not found")
        # Comp cache lookup is best-effort for now; return empty until comp persistence is wired
        return []

    @router.get("/markets/{market_id}/listings")
    def list_market_listings(market_id: str):
        market = db.get_market(market_id)
        if market is None:
            raise HTTPException(status_code=404, detail="Market not found")
        return [_hydrate_listing(l) for l in db.list_listings_for_market(market_id)]

    # ── /deals/{id}/what-if ───────────────────────────────────────────────────

    @router.post("/deals/{listing_id}/what-if")
    def what_if(listing_id: str, body: WhatIfRequest):
        listing = db.get_listing(listing_id)
        if listing is None:
            raise HTTPException(status_code=404, detail="Listing not found")

        purchase_price = body.purchase_price or listing.get("price") or 0
        arv = body.arv or listing.get("arv_likely") or (purchase_price * 1.30)
        estimated_rent = body.estimated_rent or listing.get("estimated_rent") or 0

        analysis = run_full_analysis(
            purchase_price=purchase_price,
            arv=arv,
            estimated_rent=estimated_rent,
        )

        return {
            "brrrr": {
                "purchase_price": analysis.purchase_price,
                "reno_budget": analysis.reno_budget,
                "total_all_in": analysis.total_all_in,
                "arv_used": analysis.arv_used,
                "seventy_pct_rule_pass": analysis.seventy_pct_rule_pass,
                "refi_loan": analysis.refi_loan,
                "cash_left_in_deal": analysis.cash_left_in_deal,
                "estimated_rent": analysis.estimated_rent,
                "monthly_cashflow": analysis.monthly_cashflow,
                "coc_return": analysis.coc_return,
                "dscr": analysis.dscr,
                "rent_to_price": analysis.rent_to_price,
                "grade": analysis.grade,
                "grade_reasons": analysis.grade_reasons,
            }
        }

    # ── /deals/{id}/ask ───────────────────────────────────────────────────────

    @router.post("/deals/{listing_id}/ask")
    def ask(listing_id: str, body: AskRequest):
        listing = db.get_listing(listing_id)
        if listing is None:
            raise HTTPException(status_code=404, detail="Listing not found")
        if not body.question or not body.question.strip():
            raise HTTPException(status_code=400, detail="Question must not be empty")
        answer = ask_about_deal(_hydrate_listing(listing), body.question, api_key=ANTHROPIC_API_KEY)
        return {"answer": answer}

    # ── /deals/{id}/sensitivity ───────────────────────────────────────────────

    @router.get("/deals/{listing_id}/sensitivity")
    def sensitivity(listing_id: str):
        listing = db.get_listing(listing_id)
        if listing is None:
            raise HTTPException(status_code=404, detail="Listing not found")
        return _build_sensitivity(listing)

    # ── /settings ─────────────────────────────────────────────────────────────

    @router.get("/settings")
    def get_settings():
        return dict(settings_state)

    @router.put("/settings")
    def update_settings(body: SettingsUpdate):
        for key in SETTINGS_KEYS:
            value = getattr(body, key, None)
            if value is not None:
                settings_state[key] = value
        return dict(settings_state)

    return router


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hydrate_listing(listing: dict) -> dict:
    """Flatten DB row into the shape the frontend expects."""
    out = dict(listing)
    # Re-shape brrrr fields into a nested object the frontend reads
    if any(out.get(k) is not None for k in
           ("cash_left_in_deal", "monthly_cashflow", "coc_return", "dscr", "grade")):
        out["brrrr"] = {
            "cash_left_in_deal": out.get("cash_left_in_deal"),
            "monthly_cashflow": out.get("monthly_cashflow"),
            "coc_return": out.get("coc_return"),
            "dscr": out.get("dscr"),
            "rent_to_price": out.get("rent_to_price"),
            "grade": out.get("grade"),
            "grade_reasons": [],
            "seventy_pct_rule_pass": True,
            "total_all_in": out.get("total_all_in"),
            "estimated_rent": out.get("estimated_rent"),
        }
    if out.get("arv_likely") is not None:
        out["arv"] = out["arv_likely"]
    # Parse JSON blobs
    for blob_field in ("ai_review", "negotiation_advice"):
        v = out.get(blob_field)
        if isinstance(v, str):
            try:
                out[blob_field] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                pass
    return out


def _build_sensitivity(listing: dict) -> dict:
    """Build a price x interest-rate matrix of CoC return + grade."""
    base_price = listing.get("price") or 65_000
    arv = listing.get("arv_likely") or listing.get("arv") or base_price * 1.30
    rent = listing.get("estimated_rent") or arv * 0.011

    prices = [round(base_price * mult, -2) for mult in (0.85, 0.90, 0.95, 1.00, 1.05, 1.10)]
    rates = [0.06, 0.065, 0.07, 0.075, 0.08, 0.085]

    matrix = []
    for price in prices:
        row = []
        for rate in rates:
            analysis = run_full_analysis(
                purchase_price=price, arv=arv, estimated_rent=rent
            )
            # Recompute mortgage + cashflow at this rate
            mortgage = calculate_monthly_mortgage(analysis.refi_loan, rate, 30)
            cashflow = calculate_cashflow(rent, mortgage)
            annual_cf = cashflow * 12
            coc = calculate_coc_return(annual_cf, analysis.cash_left_in_deal)
            dscr = calculate_dscr(rent * 12, mortgage * 12)
            grade, _ = grade_deal(
                cash_left=analysis.cash_left_in_deal,
                coc_return=coc,
                rent_to_price=(rent / price if price > 0 else 0),
                dscr=dscr,
                rent_achievable=True,
                seventy_pct_pass=analysis.seventy_pct_rule_pass,
            )
            row.append({
                "price": price,
                "rate": rate,
                "coc": coc,
                "dscr": dscr,
                "monthly_cashflow": cashflow,
                "grade": grade,
            })
        matrix.append(row)

    return {"prices": prices, "rates": rates, "matrix": matrix}
