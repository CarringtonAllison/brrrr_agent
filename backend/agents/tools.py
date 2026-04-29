"""Claude tool implementations for deal_analyst and negotiation_agent.

Each tool is a pure Python function returning JSON-serializable data.
External lookups (HUD, Census, FEMA) degrade gracefully on missing keys / errors.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

import httpx

from backend.brrrr_calculator import compute_max_purchase_price, run_full_analysis
from backend.config import HUD_API_KEY
from backend.motivation_detector import score_motivation

logger = logging.getLogger(__name__)


# ── Pure-math tools ───────────────────────────────────────────────────────────

def calculate_brrrr_scenarios(
    purchase_price: float,
    arv: float,
    estimated_rent: float,
) -> dict[str, Any]:
    """Run BRRRR analysis at downside / base / upside (rent and ARV ±10%).

    "Never accept numbers at face value — always run a downside scenario."
    """
    def _summarize(pp: float, a: float, r: float) -> dict[str, Any]:
        result = run_full_analysis(purchase_price=pp, arv=a, estimated_rent=r)
        return {
            "purchase_price": pp,
            "arv": a,
            "estimated_rent": r,
            "cash_left_in_deal": round(result.cash_left_in_deal, 2),
            "monthly_cashflow": round(result.monthly_cashflow, 2),
            "coc_return": round(result.coc_return, 4) if result.coc_return is not None else None,
            "dscr": round(result.dscr, 2),
            "grade": result.grade,
            "seventy_pct_rule_pass": result.seventy_pct_rule_pass,
        }

    return {
        "downside": _summarize(purchase_price, arv * 0.90, estimated_rent * 0.90),
        "base": _summarize(purchase_price, arv, estimated_rent),
        "upside": _summarize(purchase_price, arv * 1.10, estimated_rent * 1.10),
    }


def calculate_max_purchase_price_tool(
    arv: float,
    rehab_cost: float,
    max_cash_left: float = 0,
) -> dict[str, Any]:
    """Reverse-solve: max purchase price for a target cash-left in deal."""
    breakeven = compute_max_purchase_price(arv, rehab_cost, max_cash_left)
    return {
        "max_purchase_breakeven": round(breakeven, 2),
        "arv": arv,
        "rehab_cost": rehab_cost,
        "max_cash_left": max_cash_left,
    }


REHAB_PER_SQFT = {
    "light": 20,    # cosmetic — paint, carpet, fixtures
    "medium": 40,   # kitchens / baths, flooring, some systems
    "heavy": 65,    # full gut, structural, roof, mechanicals
}


def estimate_rehab_costs(sqft: int, condition: str = "medium") -> dict[str, Any]:
    """Estimate rehab cost from sqft and condition tier."""
    per_sqft = REHAB_PER_SQFT.get(condition.lower(), REHAB_PER_SQFT["medium"])
    estimate = per_sqft * sqft
    return {
        "rehab_estimate": estimate,
        "per_sqft": per_sqft,
        "sqft": sqft,
        "condition": condition,
    }


def analyze_seller_motivation(
    description: str,
    days_on_market: int = 0,
    price_drops: int = 0,
) -> dict[str, Any]:
    """Score seller motivation from description and listing metadata."""
    listing = {
        "description": description,
        "days_on_market": days_on_market,
        "price_drops": price_drops,
    }
    motivation = score_motivation(listing)
    if motivation.score >= 7:
        tier = "high"
    elif motivation.score >= 4:
        tier = "medium"
    else:
        tier = "low"
    return {
        "score": motivation.score,
        "signals": motivation.signals,
        "tier": tier,
    }


# ── External lookups ──────────────────────────────────────────────────────────

def lookup_rental_comps(zip_code: str, beds: int) -> dict[str, Any]:
    """HUD Fair Market Rent lookup by ZIP and bedroom count."""
    if not HUD_API_KEY:
        return {
            "fmr": None,
            "beds": beds,
            "zip_code": zip_code,
            "source": "hud_fmr",
            "error": "HUD_API_KEY not configured",
        }

    url = f"https://www.huduser.gov/hudapi/public/fmr/data/{zip_code}"
    try:
        resp = httpx.get(url, headers={"Authorization": f"Bearer {HUD_API_KEY}"}, timeout=10.0)
        if resp.status_code != 200:
            return {"fmr": None, "beds": beds, "zip_code": zip_code, "error": f"HTTP {resp.status_code}"}

        data = resp.json()
        bed_keys = {0: "Efficiency", 1: "One-Bedroom", 2: "Two-Bedroom", 3: "Three-Bedroom", 4: "Four-Bedroom"}
        key = bed_keys.get(beds, "Three-Bedroom")
        basicdata = data.get("data", {}).get("basicdata", [])
        if not basicdata:
            return {"fmr": None, "beds": beds, "zip_code": zip_code, "error": "no FMR data"}

        record = basicdata[0] if isinstance(basicdata, list) else basicdata
        fmr = record.get(key)
        return {"fmr": fmr, "beds": beds, "zip_code": zip_code, "source": "hud_fmr"}
    except Exception as exc:
        logger.warning(f"HUD FMR lookup failed: {exc}")
        return {"fmr": None, "beds": beds, "zip_code": zip_code, "error": str(exc)}


def lookup_property_taxes(state: str, county: str) -> dict[str, Any]:
    """Census ACS lookup for median annual property tax (B25103_001E)."""
    state_fips = _STATE_FIPS.get(state.upper())
    if not state_fips:
        return {"error": f"Unknown state: {state}"}

    url = "https://api.census.gov/data/2022/acs/acs5"
    params = {
        "get": "NAME,B25103_001E",
        "for": "county:*",
        "in": f"state:{state_fips}",
    }
    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}"}
        rows = resp.json()
        if not rows or len(rows) < 2:
            return {"error": "no data"}
        header = rows[0]
        name_idx = header.index("NAME")
        tax_idx = header.index("B25103_001E")
        for row in rows[1:]:
            if county.lower() in row[name_idx].lower():
                return {
                    "median_property_tax": float(row[tax_idx]),
                    "county": row[name_idx],
                    "source": "census_acs5",
                }
        return {"error": f"County not found: {county}"}
    except Exception as exc:
        logger.warning(f"Census property tax lookup failed: {exc}")
        return {"error": str(exc)}


def check_flood_zone(latitude: float, longitude: float) -> dict[str, Any]:
    """FEMA NFHL lookup: is this point in a Special Flood Hazard Area?"""
    url = "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query"
    params = {
        "geometry": f"{longitude},{latitude}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FLD_ZONE,ZONE_SUBTY",
        "returnGeometry": "false",
        "f": "json",
    }
    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        if resp.status_code != 200:
            return {"in_flood_zone": False, "error": f"HTTP {resp.status_code}"}
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return {"in_flood_zone": False, "zone": None}
        attrs = features[0].get("attributes", {})
        zone = attrs.get("FLD_ZONE")
        return {
            "in_flood_zone": zone in ("A", "AE", "AH", "AO", "V", "VE"),
            "zone": zone,
            "subtype": attrs.get("ZONE_SUBTY"),
            "source": "fema_nfhl",
        }
    except Exception as exc:
        logger.warning(f"FEMA flood zone lookup failed: {exc}")
        return {"in_flood_zone": False, "error": str(exc)}


def lookup_area_demographics(state: str, county: str) -> dict[str, Any]:
    """Census ACS5 lookup for median household income and home value."""
    state_fips = _STATE_FIPS.get(state.upper())
    if not state_fips:
        return {"error": f"Unknown state: {state}"}

    url = "https://api.census.gov/data/2022/acs/acs5"
    params = {
        "get": "NAME,B19013_001E,B25077_001E",
        "for": "county:*",
        "in": f"state:{state_fips}",
    }
    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}"}
        rows = resp.json()
        if not rows or len(rows) < 2:
            return {"error": "no data"}
        header = rows[0]
        name_idx = header.index("NAME")
        income_idx = header.index("B19013_001E")
        value_idx = header.index("B25077_001E")
        for row in rows[1:]:
            if county.lower() in row[name_idx].lower():
                return {
                    "median_household_income": int(row[income_idx]),
                    "median_home_value": int(row[value_idx]),
                    "county": row[name_idx],
                    "source": "census_acs5",
                }
        return {"error": f"County not found: {county}"}
    except Exception as exc:
        logger.warning(f"Census demographics lookup failed: {exc}")
        return {"error": str(exc)}


# ── Tool definitions for Anthropic API ────────────────────────────────────────

TOOL_DEFINITIONS_DEAL_ANALYST: list[dict[str, Any]] = [
    {
        "name": "calculate_brrrr_scenarios",
        "description": "Run BRRRR analysis at downside, base, and upside scenarios (ARV/rent ±10%). Use this to stress-test any deal before recommending it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "purchase_price": {"type": "number", "description": "Listing or offer price"},
                "arv": {"type": "number", "description": "After-repair value"},
                "estimated_rent": {"type": "number", "description": "Expected monthly rent"},
            },
            "required": ["purchase_price", "arv", "estimated_rent"],
        },
    },
    {
        "name": "lookup_rental_comps",
        "description": "Look up HUD Fair Market Rent for a ZIP code and bedroom count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zip_code": {"type": "string"},
                "beds": {"type": "integer"},
            },
            "required": ["zip_code", "beds"],
        },
    },
    {
        "name": "lookup_property_taxes",
        "description": "Look up median annual property tax for a US county via Census ACS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "description": "Two-letter US state abbreviation"},
                "county": {"type": "string", "description": "County name (without 'County' suffix)"},
            },
            "required": ["state", "county"],
        },
    },
    {
        "name": "check_flood_zone",
        "description": "Check if a property's lat/lon falls in a FEMA Special Flood Hazard Area.",
        "input_schema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["latitude", "longitude"],
        },
    },
    {
        "name": "calculate_max_purchase_price",
        "description": "Reverse-solve the maximum purchase price for a target cash-left-in-deal. Use this to set the ceiling for any offer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "arv": {"type": "number"},
                "rehab_cost": {"type": "number"},
                "max_cash_left": {"type": "number", "description": "Cash-left threshold; 0 = full BRRRR"},
            },
            "required": ["arv", "rehab_cost"],
        },
    },
    {
        "name": "estimate_rehab_costs",
        "description": "Estimate rehab cost from sqft and condition tier (light/medium/heavy).",
        "input_schema": {
            "type": "object",
            "properties": {
                "sqft": {"type": "integer"},
                "condition": {"type": "string", "enum": ["light", "medium", "heavy"]},
            },
            "required": ["sqft"],
        },
    },
    {
        "name": "lookup_area_demographics",
        "description": "Look up median household income and median home value for a county via Census ACS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {"type": "string"},
                "county": {"type": "string"},
            },
            "required": ["state", "county"],
        },
    },
]


TOOL_DEFINITIONS_NEGOTIATION: list[dict[str, Any]] = [
    {
        "name": "analyze_seller_motivation",
        "description": "Score seller motivation 1-10 from listing description, days on market, and price drops.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "days_on_market": {"type": "integer"},
                "price_drops": {"type": "integer"},
            },
            "required": ["description"],
        },
    },
    {
        "name": "calculate_max_purchase_price",
        "description": "Reverse-solve max purchase price for a target cash-left. Use to clamp the high end of any offer range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "arv": {"type": "number"},
                "rehab_cost": {"type": "number"},
                "max_cash_left": {"type": "number"},
            },
            "required": ["arv", "rehab_cost"],
        },
    },
]


# ── Dispatcher ────────────────────────────────────────────────────────────────

_TOOL_DISPATCH: dict[str, Callable[..., dict[str, Any]]] = {
    "calculate_brrrr_scenarios": calculate_brrrr_scenarios,
    "lookup_rental_comps": lookup_rental_comps,
    "lookup_property_taxes": lookup_property_taxes,
    "check_flood_zone": check_flood_zone,
    "calculate_max_purchase_price": calculate_max_purchase_price_tool,
    "estimate_rehab_costs": estimate_rehab_costs,
    "lookup_area_demographics": lookup_area_demographics,
    "analyze_seller_motivation": analyze_seller_motivation,
}


def run_tool(name: str, tool_input: dict[str, Any]) -> str:
    """Dispatch a tool call by name. Returns JSON-encoded result for Anthropic."""
    func = _TOOL_DISPATCH.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = func(**tool_input)
        return json.dumps(result, default=str)
    except Exception as exc:
        logger.exception(f"Tool {name} raised")
        return json.dumps({"error": str(exc), "tool": name})


# ── State FIPS lookup ─────────────────────────────────────────────────────────

_STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15",
    "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56",
}
