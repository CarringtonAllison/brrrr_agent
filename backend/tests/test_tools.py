"""Tests for agents/tools.py — Claude tool implementations.

Tools wrap pure-math helpers (BRRRR scenarios, max purchase, rehab estimate)
and external lookups (FEMA flood zone, Census demographics/taxes, HUD FMR).
External calls are mocked; pure-math is tested end-to-end.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.tools import (
    TOOL_DEFINITIONS_DEAL_ANALYST,
    TOOL_DEFINITIONS_NEGOTIATION,
    analyze_seller_motivation,
    calculate_brrrr_scenarios,
    calculate_max_purchase_price_tool,
    check_flood_zone,
    estimate_rehab_costs,
    lookup_area_demographics,
    lookup_property_taxes,
    lookup_rental_comps,
    run_tool,
)


# ── Tool definitions ──────────────────────────────────────────────────────────

class TestToolDefinitions:
    def test_deal_analyst_has_seven_tools(self):
        names = [t["name"] for t in TOOL_DEFINITIONS_DEAL_ANALYST]
        assert "calculate_brrrr_scenarios" in names
        assert "lookup_rental_comps" in names
        assert "lookup_property_taxes" in names
        assert "check_flood_zone" in names
        assert "calculate_max_purchase_price" in names
        assert "estimate_rehab_costs" in names
        assert "lookup_area_demographics" in names

    def test_negotiation_has_two_tools(self):
        names = [t["name"] for t in TOOL_DEFINITIONS_NEGOTIATION]
        assert "analyze_seller_motivation" in names
        assert "calculate_max_purchase_price" in names

    def test_each_tool_has_required_anthropic_fields(self):
        for tool in TOOL_DEFINITIONS_DEAL_ANALYST + TOOL_DEFINITIONS_NEGOTIATION:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"
            assert "properties" in tool["input_schema"]


# ── calculate_brrrr_scenarios ─────────────────────────────────────────────────

class TestCalculateBrrrScenarios:
    def test_returns_three_scenarios(self):
        result = calculate_brrrr_scenarios(
            purchase_price=65_000,
            arv=95_000,
            estimated_rent=950,
        )
        assert "downside" in result
        assert "base" in result
        assert "upside" in result

    def test_base_scenario_uses_inputs_unchanged(self):
        result = calculate_brrrr_scenarios(
            purchase_price=65_000,
            arv=95_000,
            estimated_rent=950,
        )
        assert result["base"]["purchase_price"] == 65_000
        assert result["base"]["arv"] == 95_000
        assert result["base"]["estimated_rent"] == 950
        assert "grade" in result["base"]

    def test_downside_is_worse_than_base(self):
        result = calculate_brrrr_scenarios(
            purchase_price=65_000,
            arv=95_000,
            estimated_rent=950,
        )
        # Downside: lower ARV, lower rent → worse cashflow / cash_left
        assert result["downside"]["arv"] < result["base"]["arv"]
        assert result["downside"]["estimated_rent"] < result["base"]["estimated_rent"]

    def test_upside_is_better_than_base(self):
        result = calculate_brrrr_scenarios(
            purchase_price=65_000,
            arv=95_000,
            estimated_rent=950,
        )
        assert result["upside"]["arv"] > result["base"]["arv"]
        assert result["upside"]["estimated_rent"] > result["base"]["estimated_rent"]


# ── calculate_max_purchase_price ──────────────────────────────────────────────

class TestCalculateMaxPurchasePrice:
    def test_returns_breakeven_price(self):
        result = calculate_max_purchase_price_tool(
            arv=100_000,
            rehab_cost=20_000,
            max_cash_left=0,
        )
        assert "max_purchase_breakeven" in result
        assert result["max_purchase_breakeven"] > 0

    def test_higher_max_cash_left_allows_higher_price(self):
        breakeven = calculate_max_purchase_price_tool(
            arv=100_000, rehab_cost=20_000, max_cash_left=0
        )["max_purchase_breakeven"]
        with_buffer = calculate_max_purchase_price_tool(
            arv=100_000, rehab_cost=20_000, max_cash_left=10_000
        )["max_purchase_breakeven"]
        assert with_buffer > breakeven


# ── estimate_rehab_costs ──────────────────────────────────────────────────────

class TestEstimateRehabCosts:
    def test_light_rehab_low_per_sqft(self):
        result = estimate_rehab_costs(sqft=1000, condition="light")
        assert "rehab_estimate" in result
        assert "per_sqft" in result
        assert result["per_sqft"] < 30  # light = cosmetic

    def test_heavy_rehab_higher_than_light(self):
        light = estimate_rehab_costs(sqft=1000, condition="light")["rehab_estimate"]
        heavy = estimate_rehab_costs(sqft=1000, condition="heavy")["rehab_estimate"]
        assert heavy > light

    def test_scales_with_sqft(self):
        small = estimate_rehab_costs(sqft=800, condition="medium")["rehab_estimate"]
        large = estimate_rehab_costs(sqft=2000, condition="medium")["rehab_estimate"]
        assert large > small

    def test_unknown_condition_defaults_to_medium(self):
        unknown = estimate_rehab_costs(sqft=1000, condition="bogus")["rehab_estimate"]
        medium = estimate_rehab_costs(sqft=1000, condition="medium")["rehab_estimate"]
        assert unknown == medium


# ── analyze_seller_motivation ─────────────────────────────────────────────────

class TestAnalyzeSellerMotivation:
    def test_high_signals_yield_high_score(self):
        result = analyze_seller_motivation(
            description="Must sell ASAP. Estate sale, motivated seller, will consider all offers.",
            days_on_market=180,
            price_drops=2,
        )
        assert result["score"] >= 7
        assert len(result["signals"]) > 0

    def test_no_signals_yield_low_score(self):
        result = analyze_seller_motivation(
            description="Beautiful well-maintained home in great neighborhood",
            days_on_market=5,
            price_drops=0,
        )
        assert result["score"] <= 4


# ── External lookups (mocked) ─────────────────────────────────────────────────

class TestLookupRentalComps:
    def test_hud_response_parsed(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "basicdata": [
                    {"Efficiency": 600, "One-Bedroom": 750, "Two-Bedroom": 900,
                     "Three-Bedroom": 1100, "Four-Bedroom": 1300}
                ]
            }
        }
        with patch("backend.agents.tools.HUD_API_KEY", "test-key"), \
             patch("backend.agents.tools.httpx.get", return_value=mock_resp):
            result = lookup_rental_comps(zip_code="44101", beds=3)
        assert result["fmr"] == 1100
        assert result["beds"] == 3

    def test_missing_api_key_returns_fallback(self):
        with patch("backend.agents.tools.HUD_API_KEY", ""):
            result = lookup_rental_comps(zip_code="44101", beds=3)
        assert result.get("fmr") is None
        assert "error" in result or "source" in result


class TestLookupPropertyTaxes:
    def test_census_response_parsed(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Census ACS returns header row + data row
        mock_resp.json.return_value = [
            ["NAME", "B25103_001E", "state", "county"],
            ["Cuyahoga County, Ohio", "2400", "39", "035"],
        ]
        with patch("backend.agents.tools.httpx.get", return_value=mock_resp):
            result = lookup_property_taxes(state="OH", county="Cuyahoga")
        assert "median_property_tax" in result
        assert result["median_property_tax"] == 2400.0

    def test_unknown_county_returns_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {}
        with patch("backend.agents.tools.httpx.get", return_value=mock_resp):
            result = lookup_property_taxes(state="OH", county="Bogus")
        assert "error" in result


class TestCheckFloodZone:
    def test_in_flood_zone(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "features": [{"attributes": {"FLD_ZONE": "AE", "ZONE_SUBTY": "FLOODWAY"}}]
        }
        with patch("backend.agents.tools.httpx.get", return_value=mock_resp):
            result = check_flood_zone(latitude=29.95, longitude=-90.07)
        assert result["in_flood_zone"] is True
        assert result["zone"] == "AE"

    def test_not_in_flood_zone(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"features": []}
        with patch("backend.agents.tools.httpx.get", return_value=mock_resp):
            result = check_flood_zone(latitude=41.5, longitude=-81.7)
        assert result["in_flood_zone"] is False


class TestLookupAreaDemographics:
    def test_acs_returns_demographics(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # B19013_001E = median household income, B25077_001E = median home value
        mock_resp.json.return_value = [
            ["NAME", "B19013_001E", "B25077_001E", "state", "county"],
            ["Cuyahoga County, Ohio", "55000", "150000", "39", "035"],
        ]
        with patch("backend.agents.tools.httpx.get", return_value=mock_resp):
            result = lookup_area_demographics(state="OH", county="Cuyahoga")
        assert result["median_household_income"] == 55000
        assert result["median_home_value"] == 150000


# ── run_tool dispatcher ───────────────────────────────────────────────────────

class TestRunTool:
    def test_dispatch_calculate_brrrr_scenarios(self):
        result_str = run_tool(
            "calculate_brrrr_scenarios",
            {"purchase_price": 65_000, "arv": 95_000, "estimated_rent": 950},
        )
        result = json.loads(result_str)
        assert "base" in result

    def test_dispatch_estimate_rehab_costs(self):
        result_str = run_tool(
            "estimate_rehab_costs", {"sqft": 1200, "condition": "medium"}
        )
        result = json.loads(result_str)
        assert "rehab_estimate" in result

    def test_unknown_tool_returns_error(self):
        result_str = run_tool("nonexistent_tool", {})
        result = json.loads(result_str)
        assert "error" in result
