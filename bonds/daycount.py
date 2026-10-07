"""Day count conventions and coupon schedules that place bond cash flows in time."""

from dateutil.relativedelta import relativedelta

DAY_COUNT_CONVENTIONS = ["30/360", "ACT/ACT", "ACT/360", "ACT/365"]


def days_between(start_date, end_date, convention):
    if convention != "30/360":
        return (end_date - start_date).days
    start_day = min(start_date.day, 30)
    end_day = end_date.day
    if end_day == 31 and start_day == 30:
        end_day = 30
    months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month
    return months * 30 + end_day - start_day


def days_in_coupon_period(previous_coupon, next_coupon, convention, payments_per_year):
    if convention == "ACT/ACT":
        return (next_coupon - previous_coupon).days
    if convention == "ACT/365":
        return 365 / payments_per_year
    return 360 / payments_per_year


def build_schedule(settlement_date, maturity_date, payments_per_year, convention):
    """Steps back from maturity one coupon period at a time until settlement is passed.
    Times are in years from settlement, counted in coupon periods as the market does."""
    months_per_period = 12 // payments_per_year
    day_after_maturity = maturity_date + relativedelta(days=1)
    matures_at_month_end = day_after_maturity.month != maturity_date.month
    coupon_dates = []
    coupon_date = maturity_date
    while coupon_date > settlement_date:
        coupon_dates.insert(0, coupon_date)
        months_back = len(coupon_dates) * months_per_period
        coupon_date = maturity_date - relativedelta(months=months_back)
        # A bond maturing on a month end pays every coupon on the last day of its month.
        if matures_at_month_end:
            coupon_date = coupon_date + relativedelta(day=31)
    previous_coupon = coupon_date
    next_coupon = coupon_dates[0]

    period_days = days_in_coupon_period(previous_coupon, next_coupon, convention, payments_per_year)
    accrued_days = days_between(previous_coupon, settlement_date, convention)
    # A fixed-length period can run out just before the coupon date, so one day always remains.
    remaining_days = max(period_days - accrued_days, 1)
    accrued_fraction = accrued_days / period_days
    remaining_fraction = remaining_days / period_days

    times = []
    for period in range(len(coupon_dates)):
        times.append((remaining_fraction + period) / payments_per_year)

    return {
        "previous_coupon": previous_coupon,
        "coupon_dates": coupon_dates,
        "times": times,
        "accrued_fraction": accrued_fraction,
    }
