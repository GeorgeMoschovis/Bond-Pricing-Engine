"""Checks the engine against values calculated with the Excel bond functions
and against pricing identities."""

from datetime import date

from bonds.cashflows import build_cash_flows
from bonds.curve import bootstrap_curve, discount_factor, flat_curve, forward_rate, par_bond_value
from bonds.pricing import price_bond, spread_from_price, yield_from_price
from bonds.valuation import value_bond

SAMPLE_INSTRUMENTS = [
    {"type": "Zero rate", "maturity": 0.5, "rate": 0.0425},
    {"type": "Zero rate", "maturity": 1.0, "rate": 0.0410},
    {"type": "Par yield", "maturity": 2.0, "rate": 0.0395},
    {"type": "Par yield", "maturity": 5.0, "rate": 0.0395},
    {"type": "Par yield", "maturity": 10.0, "rate": 0.0425},
    {"type": "Par yield", "maturity": 30.0, "rate": 0.0470},
]


def make_bond(bond_type, settlement_date, maturity_date, coupon_rate, day_count="30/360"):
    return {
        "type": bond_type,
        "face_value": 1000.0,
        "settlement_date": settlement_date,
        "maturity_date": maturity_date,
        "coupon_rate": coupon_rate,
        "payments_per_year": 2,
        "day_count": day_count,
    }


def make_market(curve, spread=0.0, volatility=0.01):
    return {"curve": curve, "spread": spread, "volatility": volatility, "yield_compounding": 2}


def test_price_matches_excel_price_function():
    bond = make_bond("Fixed coupon", date(2008, 2, 15), date(2017, 11, 15), 0.0575)
    report = value_bond(bond, make_market(flat_curve(0.065, 2)))
    assert abs(report["clean_price"] - 94.6343616213221) < 0.0000000001


def test_month_end_maturity_matches_excel_for_every_day_count():
    excel_prices = {
        "30/360": 101.986492247203,
        "ACT/ACT": 101.986847125501,
        "ACT/360": 101.986031935946,
        "ACT/365": 101.987048691541,
    }
    for day_count in excel_prices:
        bond = make_bond("Fixed coupon", date(2026, 3, 10), date(2034, 9, 30), 0.04125, day_count)
        report = value_bond(bond, make_market(flat_curve(0.0385, 2)))
        assert abs(report["clean_price"] - excel_prices[day_count]) < 0.0000000001


def test_accrued_interest_matches_excel_accrint_function():
    bond = make_bond("Fixed coupon", date(2026, 3, 10), date(2034, 9, 30), 0.04125, "ACT/ACT")
    report = value_bond(bond, make_market(flat_curve(0.0385, 2)))
    assert abs(report["accrued_interest"] - 1.82451923076923) < 0.0000000001


def test_zero_coupon_matches_excel_price_function():
    bond = make_bond("Zero coupon", date(2026, 3, 10), date(2041, 8, 31), 0.0, "ACT/ACT")
    report = value_bond(bond, make_market(flat_curve(0.045, 2)))
    assert abs(report["clean_price"] - 50.2299057420591) < 0.0000000001


def test_yield_matches_excel_yield_function():
    bond = make_bond("Fixed coupon", date(2008, 1, 1), date(2016, 11, 15), 0.0575)
    market = make_market(flat_curve(0.05, 2))
    report = value_bond(bond, market)
    dirty_value = (95.04287 + report["accrued_interest"]) * 10
    assert abs(yield_from_price(report["cash_flows"], dirty_value, 2) - 0.0649248093505674) < 0.0000000001


def test_durations_match_excel_duration_functions():
    long_bond = make_bond("Fixed coupon", date(2018, 7, 1), date(2048, 1, 1), 0.08, "ACT/ACT")
    long_report = value_bond(long_bond, make_market(flat_curve(0.09, 2)))
    assert abs(long_report["macaulay_duration"] - 10.9191452815919) < 0.0000000001

    # Excel differentiates exactly. The engine reprices under a 10 bp shift, so the match is close, not exact.
    short_bond = make_bond("Fixed coupon", date(2008, 1, 1), date(2016, 1, 1), 0.08, "ACT/ACT")
    short_report = value_bond(short_bond, make_market(flat_curve(0.09, 2)))
    assert abs(short_report["effective_duration"] - 5.73566981391884) < 0.0001

    modified_duration = short_report["macaulay_duration"] / (1 + 0.09 / 2)
    assert abs(modified_duration - 5.73566981391884) < 0.0000000001


def test_annual_compounding_reproduces_the_original_script():
    face_value = 1000.0
    periods = 10
    sum_of_pvs = 0.0
    for i in range(1, periods + 1):
        payment = 0.06 * face_value / 2
        if i == periods:
            payment += face_value
        sum_of_pvs += payment / (1 + 0.08) ** (i / 2)
    original_price = 100 * sum_of_pvs / face_value

    bond = make_bond("Fixed coupon", date(2026, 1, 15), date(2031, 1, 15), 0.06)
    report = value_bond(bond, make_market(flat_curve(0.08, 1)))
    assert abs(report["dirty_price"] - original_price) < 0.0000001


def test_bootstrapped_curve_reprices_every_par_instrument():
    curve = bootstrap_curve(SAMPLE_INSTRUMENTS, 2)
    for instrument in SAMPLE_INSTRUMENTS:
        if instrument["type"] == "Par yield":
            value = par_bond_value(curve, instrument["maturity"], instrument["rate"], 2)
            assert abs(value - 100) < 0.0000001


def test_par_bond_on_a_flat_curve_bootstraps_to_the_same_yield():
    curve = bootstrap_curve([{"type": "Par yield", "maturity": 10.0, "rate": 0.05}], 2)
    semiannual_equivalent = 2 * ((1 + curve["zero_rates"][0]) ** 0.5 - 1)
    assert abs(semiannual_equivalent - 0.05) < 0.0000001


def test_perpetual_equals_coupon_over_yield():
    bond = make_bond("Perpetual", date(2026, 1, 15), None, 0.05)
    bond["next_coupon_date"] = date(2026, 7, 15)
    report = value_bond(bond, make_market(flat_curve(0.04, 2)))
    assert abs(report["clean_price"] - 125.0) < 0.0000001


def test_floater_prices_at_par_when_margins_match():
    bond = make_bond("Floating rate", date(2026, 1, 15), date(2031, 1, 15), 0.0)
    bond["reference_rate"] = 0.04
    bond["quoted_margin"] = 0.012
    flat_report = value_bond(bond, make_market(flat_curve(0.04, 2), spread=0.012))
    assert abs(flat_report["clean_price"] - 100) < 0.0000001

    curve = bootstrap_curve(SAMPLE_INSTRUMENTS, 2)
    bond["reference_rate"] = forward_rate(curve, 0.0, 0.5)
    bond["quoted_margin"] = 0.0
    curve_report = value_bond(bond, make_market(curve))
    assert abs(curve_report["clean_price"] - 100) < 0.0000001
    assert curve_report["effective_duration"] < 0.5


def test_level_payment_bond_pays_the_same_amount_every_period():
    bond = make_bond("Amortising", date(2026, 1, 15), date(2031, 1, 15), 0.06)
    bond["amortisation"] = "Level payment"
    market = make_market(flat_curve(0.06, 2))
    cash_flows = build_cash_flows(bond, market)
    total_principal = 0.0
    for row in cash_flows:
        assert abs(row["total"] - cash_flows[0]["total"]) < 0.0000001
        total_principal += row["principal"]
    assert abs(total_principal - 1000.0) < 0.0000001
    assert abs(value_bond(bond, market)["clean_price"] - 100) < 0.0000001


def test_step_up_coupon_changes_on_the_step_date():
    bond = make_bond("Step-up coupon", date(2026, 1, 15), date(2030, 1, 15), 0.04)
    bond["coupon_steps"] = [{"date": date(2028, 1, 15), "coupon_rate": 0.06}]
    cash_flows = build_cash_flows(bond, make_market(flat_curve(0.05, 2)))
    assert cash_flows[3]["coupon_rate"] == 0.04
    assert cash_flows[4]["coupon_rate"] == 0.06


def test_tree_matches_discounting_and_options_move_the_price_the_right_way():
    curve = bootstrap_curve(SAMPLE_INSTRUMENTS, 2)
    market = make_market(curve, spread=0.01)
    bond = make_bond("Callable / putable", date(2026, 3, 1), date(2036, 1, 15), 0.05)
    bond["is_callable"] = False
    bond["first_call_date"] = date(2029, 1, 15)
    bond["call_price"] = 100.0
    bond["is_putable"] = False
    bond["first_put_date"] = date(2029, 1, 15)
    bond["put_price"] = 100.0

    straight_bond = dict(bond)
    straight_bond["type"] = "Fixed coupon"
    straight_value = price_bond(straight_bond, market)
    assert abs(price_bond(bond, market) - straight_value) < 0.0000001

    bond["is_callable"] = True
    callable_report = value_bond(bond, market)
    assert callable_report["option_value"] < 0
    assert callable_report["effective_duration"] < value_bond(straight_bond, market)["effective_duration"]
    assert callable_report["yield_to_worst"] <= callable_report["yield_to_maturity"]

    bond["is_callable"] = False
    bond["is_putable"] = True
    assert value_bond(bond, market)["option_value"] > 0


def test_implied_spread_recovers_the_spread_used_to_price():
    curve = bootstrap_curve(SAMPLE_INSTRUMENTS, 2)
    bond = make_bond("Fixed coupon", date(2026, 3, 1), date(2033, 9, 1), 0.045)
    dirty_value = price_bond(bond, make_market(curve, spread=0.0125))
    assert abs(spread_from_price(bond, make_market(curve), dirty_value) - 0.0125) < 0.0000001


def test_discount_factor_interpolates_between_nodes():
    curve = {"times": [1.0, 3.0], "zero_rates": [0.02, 0.04], "compounding_per_year": 1}
    assert abs(discount_factor(curve, 2.0) - 1.03 ** -2) < 0.0000000001
    assert abs(discount_factor(curve, 5.0) - 1.04 ** -5) < 0.0000000001
