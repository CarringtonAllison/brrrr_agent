"""Pydantic models for API request/response and internal data types."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── API Models (request/response) ──────────────────────────────────────────

class MarketCreate(BaseModel):
    name: str = Field(..., examples=["Cleveland OH"])
    city: str = Field(..., examples=["Cleveland"])
    state: str = Field(..., examples=["OH"])
    zip_codes: list[str] = Field(..., examples=[["44101", "44102", "44103"]])


class MarketResponse(BaseModel):
    id: str
    name: str
    city: str
    state: str
    zip_codes: list[str]
    created_at: str


class ListingSummary(BaseModel):
    id: str
    address: str
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    price: float | None = None
    beds: int | None = None
    baths: float | None = None
    sqft: int | None = None
    source: str
    grade: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    days_on_market: int | None = None
    listing_url: str | None = None


class BRRRRBreakdown(BaseModel):
    purchase_price: float
    reno_budget: float
    total_all_in: float
    arv_used: float
    seventy_pct_rule_pass: bool
    refi_loan: float
    cash_left_in_deal: float
    estimated_rent: float
    monthly_cashflow: float
    coc_return: float | None = None
    dscr: float
    rent_to_price: float
    grade: str


class WhatIfRequest(BaseModel):
    purchase_price: float | None = None
    rehab_cost: float | None = None
    arv: float | None = None
    estimated_rent: float | None = None


class WhatIfResponse(BaseModel):
    brrrr: BRRRRBreakdown


class ScanStatusResponse(BaseModel):
    scan_id: str | None = None
    is_active: bool
    market_id: str
    last_completed_at: str | None = None
