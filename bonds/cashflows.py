"""Builds the future cash flows of each supported bond type.

Every cash flow is a row holding its date, its time in years from settlement,
the coupon rate applied and the interest and principal paid."""

from dateutil.relativedelta import relativedelta

from bonds.curve import discount_factor, forward_rate
from bonds.daycount import build_schedule

BOND_TYPES = [
    "Fixed coupon",
    "Zero coupon",
    "Perpetual",
    "Floating rate",
    "Step-up coupon",
    "Amortising",
    "Callable / putable",
]
AMORTISATION_STYLES = ["Equal principal", "Level payment"]
PERPETUAL_HORIZON_YEARS = 60


def bond_schedule(bond):
    maturity_date = bond.get("maturity_date")
    if bond["type"] == "Perpetual":
        maturity_date = bond["next_coupon_date"] + relativedelta(years=PERPETUAL_HORIZON_YEARS)
    return build_schedule(bond["settlement_date"], maturity_date, bond["payments_per_year"], bond["day_count"])


def coupon_rate_for_period(bond, market, schedule, period):
    bond_type = bond["type"]
    if bond_type == "Zero coupon":
        return 0.0

    if bond_type == "Floating rate":
        # The next coupon was fixed at the last reset. Later coupons come from the curve's forward rates.
        if period == 0:
            return bond["reference_rate"] + bond["quoted_margin"]
        start_time = schedule["times"][period - 1]
        end_time = schedule["times"][period]
        return forward_rate(market["curve"], start_time, end_time) + bond["quoted_margin"]

    if bond_type == "Step-up coupon":
        period_start = schedule["previous_coupon"]
        if period > 0:
            period_start = schedule["coupon_dates"][period - 1]
        coupon_rate = bond["coupon_rate"]
        for step in bond["coupon_steps"]:
            if period_start >= step["date"]:
                coupon_rate = step["coupon_rate"]
        return coupon_rate

    return bond["coupon_rate"]


def principal_for_period(bond, outstanding, coupon_rate, remaining_periods):
    if remaining_periods == 1:
        return outstanding
    if bond["type"] != "Amortising":
        return 0.0
    periodic_rate = coupon_rate / bond["payments_per_year"]
    if bond["amortisation"] == "Equal principal" or periodic_rate == 0:
        return outstanding / remaining_periods
    level_payment = outstanding * periodic_rate / (1 - (1 + periodic_rate) ** -remaining_periods)
    return level_payment - outstanding * periodic_rate


def perpetual_terminal_value(bond, market, time):
    """Value at the horizon of every coupon paid after it, taking the curve as flat from there on."""
    period_length = 1 / bond["payments_per_year"]
    factor_now = discount_factor(market["curve"], time, market["spread"])
    factor_next = discount_factor(market["curve"], time + period_length, market["spread"])
    periodic_rate = factor_now / factor_next - 1
    coupon = bond["face_value"] * bond["coupon_rate"] * period_length
    return coupon / periodic_rate


def build_cash_flows(bond, market):
    schedule = bond_schedule(bond)
    number_of_periods = len(schedule["coupon_dates"])
    outstanding = bond["face_value"]
    cash_flows = []

    for period in range(number_of_periods):
        coupon_rate = coupon_rate_for_period(bond, market, schedule, period)
        interest = outstanding * coupon_rate / bond["payments_per_year"]
        principal = principal_for_period(bond, outstanding, coupon_rate, number_of_periods - period)
        cash_flows.append({
            "date": schedule["coupon_dates"][period],
            "time": schedule["times"][period],
            "coupon_rate": coupon_rate,
            "interest": interest,
            "principal": principal,
            "total": interest + principal,
        })
        outstanding -= principal

    if bond["type"] == "Perpetual":
        last_row = cash_flows[-1]
        last_row["principal"] = perpetual_terminal_value(bond, market, last_row["time"])
        last_row["total"] = last_row["interest"] + last_row["principal"]

    return cash_flows


def accrued_interest(bond, cash_flows):
    schedule = bond_schedule(bond)
    return cash_flows[0]["interest"] * schedule["accrued_fraction"]
