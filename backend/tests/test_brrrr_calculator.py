"""Tests for BRRRR financial calculator.

All expected values are hand-calculated to verify the formulas are correct.
"""

import pytest


from backend.brrrr_calculator import (
    calculate_reno_budget,
    calculate_all_in_cost,
    calculate_monthly_mortgage,
    calculate_refi_metrics,
    calculate_cashflow,
    calculate_coc_return,
    calculate_dscr,
    check_seventy_percent_rule,
    compute_max_purchase_price,
    grade_deal,
    run_full_analysis,
)


class TestRenoBudget:
    def test_standard_reno_22_percent(self):
        """Properties >= $50k use 22% reno budget."""
        assert calculate_reno_budget(80_000) == pytest.approx(17_600)

    def test_low_price_reno_30_percent(self):
        """Properties < $50k use 30% reno budget."""
        assert calculate_reno_budget(40_000) == pytest.approx(12_000)

    def test_boundary_at_50k(self):
        """$50k exactly uses the standard 22% rate."""
        assert calculate_reno_budget(50_000) == pytest.approx(11_000)


class TestAllInCost:
    def test_60k_property(self):
        """
        $60,000 property:
        reno = 60000 * 0.22 = 13,200
        contingency = 13200 * 0.15 = 1,980
        closing = 60000 * 0.03 = 1,800
        holding = 500 * 4 = 2,000
        total = 60000 + 13200 + 1980 + 1800 + 2000 = 78,980
        """
        result = calculate_all_in_cost(60_000)
        assert result.reno_budget == pytest.approx(13_200)
        assert result.reno_contingency == pytest.approx(1_980)
        assert result.closing_costs == pytest.approx(1_800)
        assert result.holding_costs == pytest.approx(2_000)
        assert result.total == pytest.approx(78_980)

    def test_35k_property_uses_low_reno(self):
        """
        $35,000 property (< $50k):
        reno = 35000 * 0.30 = 10,500
        contingency = 10500 * 0.15 = 1,575
        closing = 35000 * 0.03 = 1,050
        holding = 500 * 4 = 2,000
        total = 35000 + 10500 + 1575 + 1050 + 2000 = 50,125
        """
        result = calculate_all_in_cost(35_000)
        assert result.reno_budget == pytest.approx(10_500)
        assert result.total == pytest.approx(50_125)


class TestMonthlyMortgage:
    def test_standard_mortgage(self):
        """
        $86,250 at 7.5%, 30 years.
        Monthly rate = 0.075/12 = 0.00625
        Payment = 86250 * 0.00625 / (1 - (1.00625)^-360)
        Expected ≈ $603.03
        """
        payment = calculate_monthly_mortgage(86_250, 0.075, 30)
        assert payment == pytest.approx(603.03, abs=0.50)

    def test_zero_principal(self):
        assert calculate_monthly_mortgage(0, 0.075, 30) == 0.0


class TestRefiMetrics:
    def test_refi_at_115k_arv(self):
        """
        ARV = $115,000
        loan = 115000 * 0.75 = 86,250
        closing = 3,500
        cash_returned = 86250 - 3500 = 82,750
        """
        result = calculate_refi_metrics(115_000)
        assert result.loan_amount == pytest.approx(86_250)
        assert result.closing_costs == pytest.approx(3_500)
        assert result.cash_returned == pytest.approx(82_750)


class TestCashflow:
    def test_positive_cashflow(self):
        """
        rent=1050, mortgage=603
        cashflow = (1050 * 0.50) - 603 = 525 - 603 = -78
        """
        assert calculate_cashflow(1_050, 603) == pytest.approx(-78)

    def test_strong_cashflow(self):
        """
        rent=1400, mortgage=500
        cashflow = (1400 * 0.50) - 500 = 700 - 500 = 200
        """
        assert calculate_cashflow(1_400, 500) == pytest.approx(200)


class TestCoCReturn:
    def test_positive_cash_in_deal(self):
        """CoC = (200 * 12) / 10000 = 0.24 = 24%"""
        assert calculate_coc_return(200 * 12, 10_000) == pytest.approx(0.24)

    def test_zero_cash_in_deal(self):
        """If no cash left in deal, CoC is infinite (return None or inf)."""
        result = calculate_coc_return(2_400, 0)
        assert result is None or result == float('inf')

    def test_negative_cash_in_deal(self):
        """Negative cash means money was pulled out. CoC is infinite."""
        result = calculate_coc_return(2_400, -5_000)
        assert result is None or result == float('inf')


class TestDSCR:
    def test_healthy_dscr(self):
        """
        annual_rent=12600 (1050*12), annual_debt_service=7236 (603*12)
        NOI = 12600 * 0.50 = 6300
        DSCR = 6300 / 7236 ≈ 0.8707
        """
        dscr = calculate_dscr(12_600, 7_236)
        assert dscr == pytest.approx(0.8707, abs=0.01)

    def test_strong_dscr(self):
        """
        annual_rent=16800, debt_service=6000
        NOI = 16800 * 0.50 = 8400
        DSCR = 8400 / 6000 = 1.40
        """
        dscr = calculate_dscr(16_800, 6_000)
        assert dscr == pytest.approx(1.40)


class TestSeventyPercentRule:
    def test_passes(self):
        """78,980 <= 115,000 * 0.70 = 80,500 → True"""
        assert check_seventy_percent_rule(78_980, 115_000) is True

    def test_fails(self):
        """78,980 <= 110,000 * 0.70 = 77,000 → False"""
        assert check_seventy_percent_rule(78_980, 110_000) is False

    def test_exact_boundary(self):
        """Exactly at 70% should pass."""
        assert check_seventy_percent_rule(70_000, 100_000) is True


class TestMaxPurchasePrice:
    def test_breakeven(self):
        """
        ARV=115000, rehab=14300
        refi_cash = 115000 * 0.75 - 3500 = 82750
        max_price = (82750 - 14300 - 2000) / 1.03 = 66456 / 1.03 ≈ 64,521
        (holding = 500*4 = 2000)
        """
        max_price = compute_max_purchase_price(
            arv=115_000,
            rehab_cost=14_300,
            max_cash_left=0,
        )
        assert max_price == pytest.approx(64_521, abs=50)

    def test_with_cash_left_tolerance(self):
        """Allow $5k left in deal → higher max purchase."""
        price_breakeven = compute_max_purchase_price(115_000, 14_300, max_cash_left=0)
        price_5k = compute_max_purchase_price(115_000, 14_300, max_cash_left=5_000)
        assert price_5k > price_breakeven


class TestGradeDeal:
    def test_strong_deal(self):
        grade, _ = grade_deal(
            cash_left=3_000,
            coc_return=0.18,
            rent_to_price=0.014,
            dscr=1.30,
            rent_achievable=True,
            seventy_pct_pass=True,
        )
        assert grade == "STRONG"

    def test_good_deal(self):
        grade, _ = grade_deal(
            cash_left=12_000,
            coc_return=0.13,
            rent_to_price=0.011,
            dscr=1.22,
            rent_achievable=True,
            seventy_pct_pass=True,
        )
        assert grade == "GOOD"

    def test_maybe_deal(self):
        grade, _ = grade_deal(
            cash_left=20_000,
            coc_return=0.09,
            rent_to_price=0.009,
            dscr=1.12,
            rent_achievable=True,
            seventy_pct_pass=True,
        )
        assert grade == "MAYBE"

    def test_skip_when_70pct_fails(self):
        """70% rule failure → always SKIP regardless of other metrics."""
        grade, reasons = grade_deal(
            cash_left=1_000,
            coc_return=0.25,
            rent_to_price=0.015,
            dscr=1.40,
            rent_achievable=True,
            seventy_pct_pass=False,
        )
        assert grade == "SKIP"
        assert any("70%" in r for r in reasons)

    def test_skip_when_metrics_bad(self):
        grade, _ = grade_deal(
            cash_left=30_000,
            coc_return=0.05,
            rent_to_price=0.006,
            dscr=0.90,
            rent_achievable=False,
            seventy_pct_pass=True,
        )
        assert grade == "SKIP"

    def test_strong_with_negative_cash_left(self):
        """Negative cash_left means money pulled out — should be STRONG if other metrics pass."""
        grade, _ = grade_deal(
            cash_left=-3_000,
            coc_return=None,  # infinite when cash_left negative
            rent_to_price=0.015,
            dscr=1.35,
            rent_achievable=True,
            seventy_pct_pass=True,
        )
        assert grade == "STRONG"


class TestRunFullAnalysis:
    def test_complete_analysis(self):
        """Integration test: full pipeline with known inputs."""
        result = run_full_analysis(
            purchase_price=65_000,
            arv=115_000,
            estimated_rent=1_050,
        )
        assert result.purchase_price == 65_000
        assert result.total_all_in > 65_000
        assert result.arv_used == 115_000
        assert result.seventy_pct_rule_pass is True
        assert result.refi_loan == pytest.approx(86_250)
        assert result.monthly_mortgage > 0
        assert result.grade in ("STRONG", "GOOD", "MAYBE", "SKIP")
