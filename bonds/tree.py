"""Binomial interest-rate tree (Ho-Lee) for bonds with embedded call and put options.

The tree has one time step per coupon period. Node rates are continuously
compounded and move up or down with equal probability."""

import math

from bonds.curve import discount_factor


def build_rate_tree(market, step_times):
    """Returns one list of node rates per time step, lowest rate first.
    The lowest rate of each step is set so the tree reprices the discount curve exactly."""
    rate_tree = []
    # A state price is the value today of 1 paid if the tree reaches that node.
    state_prices = [1.0]

    for step in range(len(step_times) - 1):
        step_length = step_times[step + 1] - step_times[step]
        spacing = 0.0
        if step > 0:
            spacing = 2 * market["volatility"] * math.sqrt(step_times[step] / step)

        unshifted_price = 0.0
        for node in range(step + 1):
            unshifted_price += state_prices[node] * math.exp(-node * spacing * step_length)
        target_price = discount_factor(market["curve"], step_times[step + 1], market["spread"])
        lowest_rate = math.log(unshifted_price / target_price) / step_length

        step_rates = []
        next_state_prices = [0.0] * (step + 2)
        for node in range(step + 1):
            rate = lowest_rate + node * spacing
            step_rates.append(rate)
            half_value = 0.5 * state_prices[node] * math.exp(-rate * step_length)
            next_state_prices[node] += half_value
            next_state_prices[node + 1] += half_value
        rate_tree.append(step_rates)
        state_prices = next_state_prices

    return rate_tree


def tree_value(bond, market, cash_flows):
    """Rolls the bond back through the tree from maturity to settlement.
    On coupon dates inside an exercise window the value is capped at the call price
    and floored at the put price."""
    step_times = [0.0]
    for row in cash_flows:
        step_times.append(row["time"])
    rate_tree = build_rate_tree(market, step_times)
    call_value = bond["face_value"] * bond["call_price"] / 100
    put_value = bond["face_value"] * bond["put_price"] / 100

    values = [0.0] * (len(cash_flows) + 1)
    for step in range(len(cash_flows) - 1, -1, -1):
        step_length = step_times[step + 1] - step_times[step]
        payment = cash_flows[step]["total"]
        can_call = False
        can_put = False
        if step > 0:
            exercise_date = cash_flows[step - 1]["date"]
            can_call = bond["is_callable"] and exercise_date >= bond["first_call_date"]
            can_put = bond["is_putable"] and exercise_date >= bond["first_put_date"]

        new_values = []
        for node in range(step + 1):
            expected_value = 0.5 * (values[node] + values[node + 1]) + payment
            value = expected_value * math.exp(-rate_tree[step][node] * step_length)
            if can_call:
                value = min(value, call_value)
            if can_put:
                value = max(value, put_value)
            new_values.append(value)
        values = new_values

    return values[0]
