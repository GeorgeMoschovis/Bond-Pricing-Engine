"""Prices bonds from their cash flows and solves for the yield or spread a price implies.

The market is a dictionary holding the zero curve, the spread added to it, the
rate volatility used by the tree and the compounding of quoted yields."""

from bonds.cashflows import build_cash_flows
from bonds.curve import discount_factor, flat_curve
from bonds.tree import tree_value


def present_value(cash_flows, market):
    """Stores the discount factor and present value on every row and returns their total."""
    total = 0.0
    for row in cash_flows:
        row["discount_factor"] = discount_factor(market["curve"], row["time"], market["spread"])
        row["present_value"] = row["total"] * row["discount_factor"]
        total += row["present_value"]
    return total


def price_bond(bond, market):
    """Returns the dirty value in currency, which includes accrued interest."""
    cash_flows = build_cash_flows(bond, market)
    if bond["type"] == "Callable / putable":
        return tree_value(bond, market, cash_flows)
    return present_value(cash_flows, market)


def yield_from_price(cash_flows, dirty_value, compounding_per_year):
    """Bisection for the single yield that discounts the cash flows back to the dirty value."""
    low = -0.5
    high = 5.0
    for _ in range(100):
        trial_yield = (low + high) / 2
        trial_curve = flat_curve(trial_yield, compounding_per_year)
        value = 0.0
        for row in cash_flows:
            value += row["total"] * discount_factor(trial_curve, row["time"])
        if value > dirty_value:
            low = trial_yield
        else:
            high = trial_yield
    return trial_yield


def spread_from_price(bond, market, dirty_value):
    """Bisection for the spread over the curve at which the model reprices the dirty value."""
    low = -0.05
    high = 0.5
    trial_market = dict(market)
    for _ in range(50):
        trial_market["spread"] = (low + high) / 2
        if price_bond(bond, trial_market) > dirty_value:
            low = trial_market["spread"]
        else:
            high = trial_market["spread"]
    return trial_market["spread"]
