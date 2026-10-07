"""Full valuation report for one bond: prices, yields and risk measures."""

from bonds.cashflows import accrued_interest, build_cash_flows
from bonds.pricing import present_value, price_bond, spread_from_price, yield_from_price
from bonds.risk import macaulay_duration, rate_sensitivity, weighted_average_life

FIXED_SCHEDULE_TYPES = ["Fixed coupon", "Zero coupon", "Step-up coupon", "Amortising"]


def yields_to_call(bond, cash_flows, dirty_value, compounding_per_year):
    """Returns the yield to the first call date and the yield to worst,
    the lowest yield across every call date and maturity."""
    call_value = bond["face_value"] * bond["call_price"] / 100
    yield_to_first_call = None
    yield_to_worst = yield_from_price(cash_flows, dirty_value, compounding_per_year)

    for last_period in range(len(cash_flows) - 1):
        if cash_flows[last_period]["date"] < bond["first_call_date"]:
            continue
        called_flows = []
        for row in cash_flows[: last_period + 1]:
            called_flows.append({"time": row["time"], "total": row["interest"]})
        called_flows[-1]["total"] += call_value
        yield_to_this_call = yield_from_price(called_flows, dirty_value, compounding_per_year)
        if yield_to_first_call is None:
            yield_to_first_call = yield_to_this_call
        yield_to_worst = min(yield_to_worst, yield_to_this_call)

    return yield_to_first_call, yield_to_worst


def value_bond(bond, market):
    """Prices are per 100 of face. Yields and risk measures are added only where they apply to the bond type."""
    face_value = bond["face_value"]
    bond_type = bond["type"]
    compounding = market["yield_compounding"]

    cash_flows = build_cash_flows(bond, market)
    straight_value = present_value(cash_flows, market)
    dirty_value = price_bond(bond, market)
    accrued = accrued_interest(bond, cash_flows)
    clean_value = dirty_value - accrued
    duration, convexity = rate_sensitivity(bond, market, dirty_value)
    dirty_price = 100 * dirty_value / face_value

    report = {
        "cash_flows": cash_flows,
        "market_value": dirty_value,
        "dirty_price": dirty_price,
        "accrued_interest": 100 * accrued / face_value,
        "clean_price": 100 * clean_value / face_value,
        "current_yield": cash_flows[0]["coupon_rate"] * face_value / clean_value,
        "effective_duration": duration,
        "convexity": convexity,
        "dv01": duration * dirty_price * 0.0001,
    }

    if bond_type in FIXED_SCHEDULE_TYPES:
        report["yield_to_maturity"] = yield_from_price(cash_flows, dirty_value, compounding)
        report["macaulay_duration"] = macaulay_duration(cash_flows)

    if bond_type == "Amortising":
        report["weighted_average_life"] = weighted_average_life(cash_flows)

    if bond_type == "Callable / putable":
        report["yield_to_maturity"] = yield_from_price(cash_flows, dirty_value, compounding)
        report["straight_price"] = 100 * straight_value / face_value
        report["option_value"] = dirty_price - report["straight_price"]
        if bond["is_callable"]:
            yield_to_first_call, yield_to_worst = yields_to_call(bond, cash_flows, dirty_value, compounding)
            report["yield_to_worst"] = yield_to_worst
            if yield_to_first_call is not None:
                report["yield_to_call"] = yield_to_first_call

    return report


def market_price_check(bond, market, report, market_clean_price):
    """Compares the model with a market clean price and backs out the spread and yield that price implies."""
    market_dirty_price = market_clean_price + report["accrued_interest"]
    market_dirty_value = market_dirty_price * bond["face_value"] / 100
    check = {
        "model_minus_market": report["clean_price"] - market_clean_price,
        "implied_spread": spread_from_price(bond, market, market_dirty_value),
    }
    if "yield_to_maturity" in report:
        compounding = market["yield_compounding"]
        check["yield_to_maturity"] = yield_from_price(report["cash_flows"], market_dirty_value, compounding)
    return check
