"""Interest-rate risk measures: effective duration and convexity from repricing
under parallel curve shifts, Macaulay duration and weighted average life."""

from bonds.curve import shift_curve
from bonds.pricing import price_bond

RATE_SHIFT = 0.001


def shift_market(market, shift):
    shifted_market = dict(market)
    shifted_market["curve"] = shift_curve(market["curve"], shift)
    return shifted_market


def rate_sensitivity(bond, market, dirty_value):
    """Reprices the bond with the curve moved up and down and returns duration and convexity."""
    value_up = price_bond(bond, shift_market(market, RATE_SHIFT))
    value_down = price_bond(bond, shift_market(market, -RATE_SHIFT))
    duration = (value_down - value_up) / (2 * dirty_value * RATE_SHIFT)
    convexity = (value_down + value_up - 2 * dirty_value) / (dirty_value * RATE_SHIFT ** 2)
    return duration, convexity


def macaulay_duration(cash_flows):
    weighted_time = 0.0
    total_value = 0.0
    for row in cash_flows:
        weighted_time += row["time"] * row["present_value"]
        total_value += row["present_value"]
    return weighted_time / total_value


def weighted_average_life(cash_flows):
    weighted_time = 0.0
    total_principal = 0.0
    for row in cash_flows:
        weighted_time += row["time"] * row["principal"]
        total_principal += row["principal"]
    return weighted_time / total_principal
