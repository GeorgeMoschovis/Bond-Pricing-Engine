"""Streamlit interface for the bond pricing engine.

Three tabs: the bond pricer, the yield curve bootstrapper and the methodology notes."""

from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import requests
import streamlit as st
from dateutil.relativedelta import relativedelta

from bonds.cashflows import AMORTISATION_STYLES, BOND_TYPES
from bonds.curve import INSTRUMENT_TYPES, bootstrap_curve, curve_table, flat_curve
from bonds.daycount import DAY_COUNT_CONVENTIONS
from bonds.market_data import fetch_ecb_quotes, fetch_fed_quotes
from bonds.pricing import price_bond
from bonds.risk import shift_market
from bonds.valuation import market_price_check, value_bond

PROJECT_FOLDER = Path(__file__).parent
QUOTE_COLUMNS = ["type", "maturity_years", "rate_percent"]
CURVE_SOURCES = ["Fed", "ECB", "Manual"]
LIVE_SOURCE_NOTES = {
    "Fed": "US Treasury par yields with semi-annual coupons, from the Federal Reserve H.15 release.",
    "ECB": "Spot rates on AAA-rated euro area government bonds, from the European Central Bank.",
}
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]
SCENARIO_SHIFTS_BP = [-300, -250, -200, -150, -100, -50, 0, 50, 100, 150, 200, 250, 300]
EARLIEST_DATE = date(1990, 1, 1)
LATEST_DATE = date(2150, 12, 31)


def show_line_chart(frame, x_column, y_columns, y_title):
    """Line chart whose vertical axis fits the data instead of starting at zero."""
    long_frame = frame.melt(x_column, y_columns, "Series", y_title)
    colors = SERIES_COLORS[: len(y_columns)]
    chart = alt.Chart(long_frame).mark_line(point=True, tooltip=True).encode(
        x=alt.X(field=x_column, type="quantitative"),
        y=alt.Y(field=y_title, type="quantitative", scale=alt.Scale(zero=False)),
        color=alt.Color(
            field="Series",
            type="nominal",
            scale=alt.Scale(domain=y_columns, range=colors),
            legend=alt.Legend(title=None, orient="bottom"),
        ),
    )
    st.altair_chart(chart)


@st.cache_data(ttl=3600)
def load_live_quotes(source):
    """Downloads the quotes of one source and keeps them for an hour."""
    if source == "Fed":
        return fetch_fed_quotes()
    return fetch_ecb_quotes()


st.set_page_config(page_title="Bond Pricing Engine", layout="wide")
st.title("Bond Pricing Engine")
st.caption("Bond valuation, risk measures and yield-curve bootstrapping.")

pricer_tab, curve_tab, methodology_tab = st.tabs(["Bond pricer", "Yield curve", "Methodology"])

with curve_tab:
    st.subheader("Market quotes")
    curve_source = st.segmented_control("Source", CURVE_SOURCES, default="Fed", required=True)
    st.write(
        "Zero rates are used as quoted, with annual compounding. "
        "Par yields are bootstrapped into zero rates, shortest maturity first."
    )

    quotes = None
    if curve_source == "Manual":
        uploaded_file = st.file_uploader(
            "Replace the sample quotes with a CSV or Excel file (columns: type, maturity_years, rate_percent)",
            type=["csv", "xlsx"],
        )
        if uploaded_file is None:
            quotes = pd.read_csv(PROJECT_FOLDER / "data" / "sample_curve.csv")
        elif uploaded_file.name.lower().endswith(".xlsx"):
            quotes = pd.read_excel(uploaded_file)
        else:
            quotes = pd.read_csv(uploaded_file)
        if list(quotes.columns) != QUOTE_COLUMNS:
            st.error("The file needs exactly these columns: type, maturity_years, rate_percent.")
            quotes = None
    else:
        if st.button("Refresh"):
            load_live_quotes.clear()
        try:
            quotes, quote_date = load_live_quotes(curve_source)
            st.caption(f"{LIVE_SOURCE_NOTES[curve_source]} Quotes of {quote_date}.")
        except requests.RequestException:
            st.error("The quotes could not be downloaded. Check the internet connection or switch to Manual.")

    zero_curve = None
    if quotes is not None:
        quote_column_config = {
            "type": st.column_config.SelectboxColumn("Instrument", options=INSTRUMENT_TYPES, required=True),
            "maturity_years": st.column_config.NumberColumn("Maturity (years)", min_value=0.01, required=True),
            "rate_percent": st.column_config.NumberColumn("Rate (%)", format="%.3f", required=True),
        }
        quote_column, result_column = st.columns([1, 2], gap="large")
        with quote_column:
            # Treasury par yields assume two coupons per year. ECB quotes are zero rates and need none.
            par_frequency = 2
            if curve_source == "Manual":
                quotes = st.data_editor(
                    quotes, num_rows="dynamic", hide_index=True, column_config=quote_column_config
                )
                par_frequency = st.selectbox("Coupon payments per year on par instruments", [1, 2, 4], index=1)
            else:
                st.dataframe(quotes, hide_index=True, column_config=quote_column_config, height="content")

        valid_quotes = quotes.dropna()
        valid_quotes = valid_quotes[valid_quotes["type"].isin(INSTRUMENT_TYPES)]
        valid_quotes = valid_quotes.drop_duplicates("maturity_years")
        valid_quotes = valid_quotes.sort_values("maturity_years")
        instruments = []
        for _, quote in valid_quotes.iterrows():
            instruments.append({
                "type": quote["type"],
                "maturity": float(quote["maturity_years"]),
                "rate": float(quote["rate_percent"]) / 100,
            })

        with result_column:
            if len(instruments) == 0:
                st.error("Enter at least one quote to build the curve.")
            else:
                zero_curve = bootstrap_curve(instruments, par_frequency)
                curve_frame = pd.DataFrame(curve_table(zero_curve, instruments))
                for column in ["market_quote", "zero_rate", "forward_rate"]:
                    curve_frame[column] = curve_frame[column] * 100
                curve_frame.columns = [
                    "Maturity (years)",
                    "Instrument",
                    "Market quote (%)",
                    "Zero rate (%)",
                    "Forward rate (%)",
                    "Discount factor",
                ]
                rate_columns = ["Market quote (%)", "Zero rate (%)", "Forward rate (%)"]
                show_line_chart(curve_frame, "Maturity (years)", rate_columns, "Rate (%)")
                st.caption("The forward rate at each maturity is the rate implied between the previous maturity and that one.")
                st.dataframe(curve_frame.round(6), hide_index=True, height="content")
                st.download_button(
                    "Download zero curve (CSV)",
                    curve_frame.to_csv(index=False),
                    "zero_curve.csv",
                    "text/csv",
                )

with methodology_tab:
    methodology_file = PROJECT_FOLDER / "docs" / "bond_valuation_methodology.md"
    st.markdown(methodology_file.read_text(encoding="utf-8"))

with pricer_tab:
    input_column, output_column = st.columns([1, 2], gap="large")

    with input_column:
        st.subheader("Bond")
        today = date.today()
        bond_type = st.selectbox("Bond type", BOND_TYPES)
        face_value = st.number_input("Face value", min_value=1.0, value=1000.0, step=100.0)
        settlement_date = st.date_input("Settlement date", today, min_value=EARLIEST_DATE, max_value=LATEST_DATE)
        payments_per_year = st.selectbox("Coupon payments per year", [1, 2, 4, 12], index=1)
        day_count = st.selectbox("Day count convention", DAY_COUNT_CONVENTIONS)

        bond = {
            "type": bond_type,
            "face_value": face_value,
            "settlement_date": settlement_date,
            "payments_per_year": payments_per_year,
            "day_count": day_count,
            "coupon_rate": 0.0,
        }

        if bond_type == "Perpetual":
            bond["next_coupon_date"] = st.date_input(
                "Next coupon date", today + relativedelta(months=6), min_value=EARLIEST_DATE, max_value=LATEST_DATE
            )
        else:
            bond["maturity_date"] = st.date_input(
                "Maturity date", today + relativedelta(years=10), min_value=EARLIEST_DATE, max_value=LATEST_DATE
            )

        if bond_type == "Floating rate":
            bond["reference_rate"] = st.number_input("Current reference rate (%)", value=4.0, step=0.05) / 100
            bond["quoted_margin"] = st.number_input("Quoted margin (bp)", value=100.0, step=5.0) / 10000
        elif bond_type != "Zero coupon":
            bond["coupon_rate"] = st.number_input(
                "Coupon rate (%)", min_value=0.0, value=5.0, step=0.125, format="%.3f"
            ) / 100

        if bond_type == "Step-up coupon":
            st.write("Coupon steps. Each rate applies to coupon periods starting on or after its date.")
            default_steps = pd.DataFrame({
                "step_date": [today + relativedelta(years=3), today + relativedelta(years=6)],
                "coupon_percent": [6.0, 7.0],
            })
            edited_steps = st.data_editor(
                default_steps,
                num_rows="dynamic",
                hide_index=True,
                column_config={
                    "step_date": st.column_config.DateColumn("Step date", required=True),
                    "coupon_percent": st.column_config.NumberColumn("Coupon (%)", min_value=0.0, required=True),
                },
            )
            valid_steps = edited_steps.dropna()
            valid_steps = valid_steps.sort_values("step_date")
            bond["coupon_steps"] = []
            for _, step in valid_steps.iterrows():
                bond["coupon_steps"].append({
                    "date": pd.to_datetime(step["step_date"]).date(),
                    "coupon_rate": float(step["coupon_percent"]) / 100,
                })

        if bond_type == "Amortising":
            bond["amortisation"] = st.selectbox("Amortisation", AMORTISATION_STYLES)

        if bond_type == "Callable / putable":
            first_exercise_date = today + relativedelta(years=3)
            bond["is_callable"] = st.checkbox("Callable by the issuer", value=True)
            no_call = not bond["is_callable"]
            bond["first_call_date"] = st.date_input(
                "First call date", first_exercise_date, min_value=EARLIEST_DATE, max_value=LATEST_DATE, disabled=no_call
            )
            bond["call_price"] = st.number_input(
                "Call price (per 100)", min_value=0.0, value=100.0, step=0.5, disabled=no_call
            )
            bond["is_putable"] = st.checkbox("Putable by the investor", value=False)
            no_put = not bond["is_putable"]
            bond["first_put_date"] = st.date_input(
                "First put date", first_exercise_date, min_value=EARLIEST_DATE, max_value=LATEST_DATE, disabled=no_put
            )
            bond["put_price"] = st.number_input(
                "Put price (per 100)", min_value=0.0, value=100.0, step=0.5, disabled=no_put
            )

        st.subheader("Market")
        curve_choice = st.radio("Discount curve", ["Flat yield", "Bootstrapped zero curve"], horizontal=True)
        compounding_choice = st.selectbox("Yield compounding", ["Same as coupon frequency", "Annual"])
        yield_compounding = 1
        if compounding_choice == "Same as coupon frequency":
            yield_compounding = payments_per_year

        discount_curve = zero_curve
        if curve_choice == "Flat yield":
            flat_yield = st.number_input("Yield (%)", min_value=-5.0, max_value=100.0, value=5.0, step=0.05) / 100
            discount_curve = flat_curve(flat_yield, yield_compounding)
        else:
            st.caption(f"Uses the {curve_source} quotes selected in the Yield curve tab.")
        spread = st.number_input(
            "Spread over curve (bp)",
            min_value=-500.0,
            max_value=5000.0,
            value=0.0,
            step=5.0,
            help="Added to every zero rate. It is the Z-spread of a plain bond and the option-adjusted "
            "spread of a callable or putable bond. For a floater it plays the role of the discount margin.",
        ) / 10000
        volatility = 0.0
        if bond_type == "Callable / putable":
            volatility = st.number_input(
                "Rate volatility (bp per year)",
                min_value=0.0,
                value=100.0,
                step=5.0,
                help="Standard deviation of annual changes in the short rate, in basis points.",
            ) / 10000
        market_clean_price = st.number_input(
            "Market clean price to compare (0 to skip)", min_value=0.0, value=0.0, step=0.25
        )

        market = {
            "curve": discount_curve,
            "spread": spread,
            "volatility": volatility,
            "yield_compounding": yield_compounding,
        }

    with output_column:
        if discount_curve is None:
            st.error("The zero curve could not be built. Check the quotes in the Yield curve tab.")
            st.stop()
        if bond_type != "Perpetual" and bond["maturity_date"] <= settlement_date:
            st.error("The maturity date must be after the settlement date.")
            st.stop()

        report = None
        try:
            report = value_bond(bond, market)
        except ZeroDivisionError:
            pass
        if report is None or report["dirty_price"] <= 0:
            st.error("These inputs do not produce a valid price. Check the rates, the spread and the dates.")
            st.stop()

        st.subheader("Valuation")
        figures = [
            ("Clean price", f"{report['clean_price']:.4f}"),
            ("Accrued interest", f"{report['accrued_interest']:.4f}"),
            ("Dirty price", f"{report['dirty_price']:.4f}"),
            ("Market value", f"{report['market_value']:,.2f}"),
        ]
        if "yield_to_maturity" in report:
            figures.append(("Yield to maturity", f"{report['yield_to_maturity']:.4%}"))
        figures.append(("Current yield", f"{report['current_yield']:.4%}"))
        if "yield_to_call" in report:
            figures.append(("Yield to first call", f"{report['yield_to_call']:.4%}"))
        if "yield_to_worst" in report:
            figures.append(("Yield to worst", f"{report['yield_to_worst']:.4%}"))
        if "straight_price" in report:
            figures.append(("Option-free dirty price", f"{report['straight_price']:.4f}"))
            figures.append(("Embedded option value", f"{report['option_value']:.4f}"))
        if "macaulay_duration" in report:
            figures.append(("Macaulay duration", f"{report['macaulay_duration']:.4f}"))
        figures.append(("Effective duration", f"{report['effective_duration']:.4f}"))
        figures.append(("Convexity", f"{report['convexity']:.4f}"))
        figures.append(("DV01 (per 100 face)", f"{report['dv01']:.5f}"))
        if "weighted_average_life" in report:
            figures.append(("Weighted average life", f"{report['weighted_average_life']:.4f}"))

        figure_columns = st.columns(4)
        for position in range(len(figures)):
            label, text = figures[position]
            figure_columns[position % 4].metric(label, text)
        st.caption("Prices are per 100 of face value. Market value is the dirty price applied to the face value.")

        if market_clean_price > 0:
            check = market_price_check(bond, market, report, market_clean_price)
            st.subheader("Market price comparison")
            check_columns = st.columns(4)
            check_columns[0].metric("Model minus market", f"{check['model_minus_market']:+.4f}")
            check_columns[1].metric("Implied spread over curve", f"{check['implied_spread'] * 10000:.1f} bp")
            if "yield_to_maturity" in check:
                check_columns[2].metric("Yield to maturity at market price", f"{check['yield_to_maturity']:.4%}")

        cash_flow_tab, scenario_tab = st.tabs(["Cash flows", "Rate scenarios"])

        with cash_flow_tab:
            cash_flow_frame = pd.DataFrame(report["cash_flows"])
            cash_flow_frame["coupon_rate"] = cash_flow_frame["coupon_rate"] * 100
            cash_flow_frame = cash_flow_frame.round(6)
            cash_flow_frame["date"] = pd.to_datetime(cash_flow_frame["date"])
            cash_flow_frame.columns = [
                "Date",
                "Time (years)",
                "Coupon rate (%)",
                "Interest",
                "Principal",
                "Total",
                "Discount factor",
                "Present value",
            ]
            st.bar_chart(
                cash_flow_frame,
                x="Date",
                y=["Interest", "Principal"],
                y_label="Cash flow",
                color=SERIES_COLORS[:2],
            )
            if bond_type == "Perpetual":
                st.caption("The last row holds the value at that date of all later coupons, shown as principal.")
            if bond_type == "Callable / putable":
                st.caption("Cash flows and present values are shown to maturity, before any call or put.")
            st.dataframe(
                cash_flow_frame,
                hide_index=True,
                column_config={"Date": st.column_config.DateColumn(format="YYYY-MM-DD")},
            )

        with scenario_tab:
            st.write("The bond is repriced after moving the whole discount curve up or down in parallel.")
            option_free_bond = dict(bond)
            option_free_bond["type"] = "Fixed coupon"
            scenario_rows = []
            for shift_bp in SCENARIO_SHIFTS_BP:
                shifted_market = shift_market(market, shift_bp / 10000)
                shifted_price = 100 * price_bond(bond, shifted_market) / face_value
                row = {"Rate shift (bp)": shift_bp, "Dirty price": shifted_price}
                if bond_type == "Callable / putable":
                    row["Option-free dirty price"] = 100 * price_bond(option_free_bond, shifted_market) / face_value
                row["Change (%)"] = 100 * (shifted_price / report["dirty_price"] - 1)
                scenario_rows.append(row)
            scenario_frame = pd.DataFrame(scenario_rows)

            price_columns = ["Dirty price"]
            if bond_type == "Callable / putable":
                price_columns.append("Option-free dirty price")
            show_line_chart(scenario_frame, "Rate shift (bp)", price_columns, "Price per 100")
            st.dataframe(scenario_frame.round(4), hide_index=True)
