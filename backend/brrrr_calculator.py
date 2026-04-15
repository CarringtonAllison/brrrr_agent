"""Pure BRRRR financial calculator.

All functions are pure math — no side effects, no API calls, no database access.
This module is the financial engine that everything else depends on.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Constants (defaults, can be overridden via config) ──────────────────────

RENO_PERCENT = 0.22
RENO_PERCENT_LOW = 0.30
LOW_PRICE_THRESHOLD = 50_000
RENO_CONTINGENCY = 0.15
CLOSING_COST_PERCENT = 0.03
MONTHLY_HOLD_COST = 500
REHAB_MONTHS = 4
REFI_LTV = 0.75
REFI_CLOSING_FLAT = 3_500
INTEREST_RATE = 0.075
LOAN_TERM_YEARS = 30
EXPENSE_RATIO = 0.50

# Grading thresholds
GRADE_STRONG = {"cash_left": 5_000, "coc": 0.15, "rent_ratio": 0.012, "dscr": 1.25}
GRADE_GOOD = {"cash_left": 15_000, "coc": 0.12, "rent_ratio": 0.010, "dscr": 1.20}
GRADE_MAYBE = {"cash_left": 25_000, "coc": 0.08, "rent_ratio": 0.008, "dscr": 1.10}


# ── Data classes ────────────────────────────────────────────────────────────

@dataclass
class AllInCost:
    purchase_price: float
    reno_budget: float
    reno_contingency: float
    closing_costs: float
    holding_costs: float
    total: float


@dataclass
class RefiMetrics:
    arv: float
    loan_amount: float
    closing_costs: float
    cash_returned: float


@dataclass
class BRRRRAnalysis:
    purchase_price: float
    reno_budget: float
    reno_contingency: float
    closing_costs: float
    holding_costs: float
    total_all_in: float
    arv_used: float
    seventy_pct_rule_pass: bool
    refi_loan: float
    refi_closing: float
    cash_returned: float
    cash_left_in_deal: float
    estimated_rent: float
    rent_achievable: bool
    monthly_mortgage: float
    monthly_cashflow: float
    annual_cashflow: float
    coc_return: float | None
    dscr: float
    rent_to_price: float
    grade: str
    grade_reasons: list[str]


# ── Core calculation functions ──────────────────────────────────────────────

def calculate_reno_budget(price: float) -> float:
    """Calculate renovation budget based on purchase price.

    Uses 30% for properties under $50k, 22% for $50k+.
    """
    rate = RENO_PERCENT_LOW if price < LOW_PRICE_THRESHOLD else RENO_PERCENT
    return price * rate


def calculate_all_in_cost(price: float) -> AllInCost:
    """Calculate total investment cost including rehab, closing, and holding."""
    reno = calculate_reno_budget(price)
    contingency = reno * RENO_CONTINGENCY
    closing = price * CLOSING_COST_PERCENT
    holding = MONTHLY_HOLD_COST * REHAB_MONTHS
    total = price + reno + contingency + closing + holding
    return AllInCost(
        purchase_price=price,
        reno_budget=reno,
        reno_contingency=contingency,
        closing_costs=closing,
        holding_costs=holding,
        total=total,
    )


def calculate_monthly_mortgage(principal: float, rate: float, years: int) -> float:
    """Calculate monthly mortgage payment using standard amortization formula."""
    if principal <= 0:
        return 0.0
    monthly_rate = rate / 12
    num_payments = years * 12
    return principal * (monthly_rate / (1 - (1 + monthly_rate) ** -num_payments))


def calculate_refi_metrics(arv: float) -> RefiMetrics:
    """Calculate refinance loan amount, closing costs, and cash returned."""
    loan = arv * REFI_LTV
    closing = REFI_CLOSING_FLAT
    cash_returned = loan - closing
    return RefiMetrics(
        arv=arv,
        loan_amount=loan,
        closing_costs=closing,
        cash_returned=cash_returned,
    )


def calculate_cashflow(rent: float, mortgage: float) -> float:
    """Calculate monthly cashflow using the 50% expense rule.

    cashflow = (rent * 0.50) - mortgage
    """
    return (rent * EXPENSE_RATIO) - mortgage


def calculate_coc_return(annual_cashflow: float, cash_in_deal: float) -> float | None:
    """Calculate cash-on-cash return.

    Returns None if cash_in_deal is zero or negative (infinite return).
    """
    if cash_in_deal <= 0:
        return None
    return annual_cashflow / cash_in_deal


def calculate_dscr(annual_rent: float, annual_debt_service: float) -> float:
    """Calculate Debt Service Coverage Ratio.

    DSCR = NOI / annual_debt_service
    NOI = annual_rent * expense_ratio (using 50% rule for NOI)
    """
    if annual_debt_service <= 0:
        return float('inf')
    noi = annual_rent * EXPENSE_RATIO
    return noi / annual_debt_service


def check_seventy_percent_rule(total_all_in: float, arv: float) -> bool:
    """Check if total investment is within 70% of ARV."""
    return total_all_in <= arv * 0.70


def compute_max_purchase_price(
    arv: float,
    rehab_cost: float,
    max_cash_left: float = 0,
) -> float:
    """Reverse-solve: what's the highest purchase price for a target cash-left?

    Solves: price + rehab + contingency + closing + holding - refi_cash = max_cash_left
    Where:
        contingency = rehab * 0.15  (already included in rehab_cost param)
        closing = price * 0.03
        holding = monthly_hold * months
        refi_cash = arv * 0.75 - 3500

    Rearranging:
        price * (1 + closing_pct) = refi_cash - rehab_cost - holding + max_cash_left
        price = numerator / (1 + closing_pct)
    """
    refi_cash = arv * REFI_LTV - REFI_CLOSING_FLAT
    holding = MONTHLY_HOLD_COST * REHAB_MONTHS
    numerator = refi_cash - rehab_cost - holding + max_cash_left
    return max(0, numerator / (1 + CLOSING_COST_PERCENT))


# ── Deal grading ────────────────────────────────────────────────────────────

def grade_deal(
    cash_left: float,
    coc_return: float | None,
    rent_to_price: float,
    dscr: float,
    rent_achievable: bool,
    seventy_pct_pass: bool,
) -> tuple[str, list[str]]:
    """Grade a deal based on BRRRR metrics.

    Returns (grade, list_of_reasons).
    """
    reasons: list[str] = []

    if not seventy_pct_pass:
        reasons.append("70% rule failed — total all-in exceeds 70% of ARV")
        return ("SKIP", reasons)

    # Treat None/negative cash_left CoC as infinite (excellent)
    effective_coc = float('inf') if coc_return is None else coc_return

    # STRONG
    if (
        cash_left <= GRADE_STRONG["cash_left"]
        and effective_coc >= GRADE_STRONG["coc"]
        and rent_to_price >= GRADE_STRONG["rent_ratio"]
        and dscr >= GRADE_STRONG["dscr"]
        and rent_achievable
    ):
        reasons.append("All STRONG thresholds met")
        return ("STRONG", reasons)

    # GOOD
    if (
        cash_left <= GRADE_GOOD["cash_left"]
        and effective_coc >= GRADE_GOOD["coc"]
        and rent_to_price >= GRADE_GOOD["rent_ratio"]
        and dscr >= GRADE_GOOD["dscr"]
    ):
        reasons.append("All GOOD thresholds met")
        return ("GOOD", reasons)

    # MAYBE
    if (
        cash_left <= GRADE_MAYBE["cash_left"]
        and effective_coc >= GRADE_MAYBE["coc"]
        and rent_to_price >= GRADE_MAYBE["rent_ratio"]
        and dscr >= GRADE_MAYBE["dscr"]
    ):
        reasons.append("Meets MAYBE thresholds")
        return ("MAYBE", reasons)

    # SKIP
    if cash_left > GRADE_MAYBE["cash_left"]:
        reasons.append(f"Cash left ${cash_left:,.0f} exceeds ${GRADE_MAYBE['cash_left']:,} threshold")
    if effective_coc < GRADE_MAYBE["coc"]:
        reasons.append(f"CoC {effective_coc:.1%} below {GRADE_MAYBE['coc']:.0%} minimum")
    if rent_to_price < GRADE_MAYBE["rent_ratio"]:
        reasons.append(f"Rent-to-price {rent_to_price:.2%} below {GRADE_MAYBE['rent_ratio']:.1%} minimum")
    if dscr < GRADE_MAYBE["dscr"]:
        reasons.append(f"DSCR {dscr:.2f} below {GRADE_MAYBE['dscr']} minimum")
    return ("SKIP", reasons)


# ── Full analysis orchestrator ──────────────────────────────────────────────

def run_full_analysis(
    purchase_price: float,
    arv: float,
    estimated_rent: float,
    market_rent: float | None = None,
) -> BRRRRAnalysis:
    """Run the complete BRRRR analysis pipeline.

    Args:
        purchase_price: Listing price
        arv: After Repair Value (from comp analysis)
        estimated_rent: Expected monthly rent
        market_rent: Actual market rent for validation (optional)
    """
    # Step 1: Calculate all-in cost
    all_in = calculate_all_in_cost(purchase_price)

    # Step 2: Check 70% rule
    seventy_pct_pass = check_seventy_percent_rule(all_in.total, arv)

    # Step 3: Refi metrics
    refi = calculate_refi_metrics(arv)
    cash_left = all_in.total - refi.cash_returned

    # Step 4: Monthly mortgage on refi loan
    mortgage = calculate_monthly_mortgage(refi.loan_amount, INTEREST_RATE, LOAN_TERM_YEARS)

    # Step 5: Cashflow
    monthly_cf = calculate_cashflow(estimated_rent, mortgage)
    annual_cf = monthly_cf * 12

    # Step 6: CoC return
    coc = calculate_coc_return(annual_cf, cash_left)

    # Step 7: DSCR
    annual_rent = estimated_rent * 12
    annual_debt = mortgage * 12
    dscr = calculate_dscr(annual_rent, annual_debt)

    # Step 8: Rent-to-price ratio
    rent_to_price = estimated_rent / purchase_price if purchase_price > 0 else 0

    # Step 9: Rent achievability
    rent_achievable = True
    if market_rent is not None:
        rent_achievable = estimated_rent <= market_rent * 1.10

    # Step 10: Grade
    grade, reasons = grade_deal(
        cash_left=cash_left,
        coc_return=coc,
        rent_to_price=rent_to_price,
        dscr=dscr,
        rent_achievable=rent_achievable,
        seventy_pct_pass=seventy_pct_pass,
    )

    return BRRRRAnalysis(
        purchase_price=purchase_price,
        reno_budget=all_in.reno_budget,
        reno_contingency=all_in.reno_contingency,
        closing_costs=all_in.closing_costs,
        holding_costs=all_in.holding_costs,
        total_all_in=all_in.total,
        arv_used=arv,
        seventy_pct_rule_pass=seventy_pct_pass,
        refi_loan=refi.loan_amount,
        refi_closing=refi.closing_costs,
        cash_returned=refi.cash_returned,
        cash_left_in_deal=cash_left,
        estimated_rent=estimated_rent,
        rent_achievable=rent_achievable,
        monthly_mortgage=mortgage,
        monthly_cashflow=monthly_cf,
        annual_cashflow=annual_cf,
        coc_return=coc,
        dscr=dscr,
        rent_to_price=rent_to_price,
        grade=grade,
        grade_reasons=reasons,
    )
