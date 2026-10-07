"""Zero-coupon yield curve: bootstrapping from market quotes, interpolation,
discount factors and forward rates.

A curve is a dictionary holding the node times in years, the zero rate at each
node and the compounding frequency of those rates."""

import math

INSTRUMENT_TYPES = ["Zero rate", "Par yield"]


def flat_curve(rate, compounding_per_year):
    return {"times": [1.0], "zero_rates": [rate], "compounding_per_year": compounding_per_year}


def shift_curve(curve, shift):
    shifted_rates = []
    for rate in curve["zero_rates"]:
        shifted_rates.append(rate + shift)
    return {
        "times": curve["times"],
        "zero_rates": shifted_rates,
        "compounding_per_year": curve["compounding_per_year"],
    }


def interpolate_zero_rate(curve, time):
    """Linear interpolation between nodes, flat before the first node and after the last."""
    times = curve["times"]
    rates = curve["zero_rates"]
    if time <= times[0]:
        return rates[0]
    if time >= times[-1]:
        return rates[-1]
    for node in range(1, len(times)):
        if time <= times[node]:
            weight = (time - times[node - 1]) / (times[node] - times[node - 1])
            return rates[node - 1] + weight * (rates[node] - rates[node - 1])


def discount_factor(curve, time, spread=0.0):
    rate = interpolate_zero_rate(curve, time) + spread
    compounding = curve["compounding_per_year"]
    return (1 + rate / compounding) ** (-compounding * time)


def forward_rate(curve, start_time, end_time):
    """Simple-interest rate the curve implies between two future times."""
    growth = discount_factor(curve, start_time) / discount_factor(curve, end_time)
    return (growth - 1) / (end_time - start_time)


def par_bond_value(curve, maturity, coupon_rate, payments_per_year):
    """Dirty value per 100 of face of a bond whose coupon dates are counted back from maturity."""
    coupon = 100 * coupon_rate / payments_per_year
    number_of_coupons = math.ceil(maturity * payments_per_year - 1e-9)
    value = 100 * discount_factor(curve, maturity)
    for coupon_number in range(number_of_coupons):
        coupon_time = maturity - coupon_number / payments_per_year
        value += coupon * discount_factor(curve, coupon_time)
    return value


def bootstrap_curve(instruments, payments_per_year):
    """Builds the zero curve one maturity at a time, shortest first.
    A zero rate is used as quoted. For a par yield, bisection finds the zero rate
    at which a bond paying that yield as its coupon is worth par."""
    curve = {"times": [], "zero_rates": [], "compounding_per_year": 1}
    for instrument in instruments:
        maturity = instrument["maturity"]
        zero_rate = instrument["rate"]
        if instrument["type"] == "Par yield":
            # Par is a clean price, so interest accrued in a short first period is added to the target.
            number_of_coupons = math.ceil(maturity * payments_per_year - 1e-9)
            elapsed_fraction = number_of_coupons - maturity * payments_per_year
            target_value = 100 + 100 * instrument["rate"] / payments_per_year * elapsed_fraction
            low = -0.05
            high = 1.0
            for _ in range(60):
                zero_rate = (low + high) / 2
                trial_curve = {
                    "times": curve["times"] + [maturity],
                    "zero_rates": curve["zero_rates"] + [zero_rate],
                    "compounding_per_year": 1,
                }
                value = par_bond_value(trial_curve, maturity, instrument["rate"], payments_per_year)
                if value > target_value:
                    low = zero_rate
                else:
                    high = zero_rate
        curve["times"].append(maturity)
        curve["zero_rates"].append(zero_rate)
    return curve


def curve_table(curve, instruments):
    """One row per node with its discount factor and the forward rate from the previous node."""
    rows = []
    previous_time = 0.0
    previous_factor = 1.0
    for node in range(len(curve["times"])):
        time = curve["times"][node]
        factor = discount_factor(curve, time)
        forward = (previous_factor / factor) ** (1 / (time - previous_time)) - 1
        rows.append({
            "maturity": time,
            "instrument": instruments[node]["type"],
            "market_quote": instruments[node]["rate"],
            "zero_rate": curve["zero_rates"][node],
            "forward_rate": forward,
            "discount_factor": factor,
        })
        previous_time = time
        previous_factor = factor
    return rows
