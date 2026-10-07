"""Live yield curve quotes from the Federal Reserve and the European Central Bank.

Each function returns the latest quotes as a table with the columns type,
maturity_years and rate_percent, together with the date of those quotes."""

import io
import math
from datetime import date, timedelta

import pandas as pd
import requests

FED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
ECB_URL = "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM."
TIMEOUT_SECONDS = 20

FED_MATURITIES = {
    "DGS1MO": 1 / 12,
    "DGS3MO": 0.25,
    "DGS6MO": 0.5,
    "DGS1": 1.0,
    "DGS2": 2.0,
    "DGS3": 3.0,
    "DGS5": 5.0,
    "DGS7": 7.0,
    "DGS10": 10.0,
    "DGS20": 20.0,
    "DGS30": 30.0,
}
ECB_MATURITIES = {
    "SR_3M": 0.25,
    "SR_6M": 0.5,
    "SR_1Y": 1.0,
    "SR_2Y": 2.0,
    "SR_3Y": 3.0,
    "SR_5Y": 5.0,
    "SR_7Y": 7.0,
    "SR_10Y": 10.0,
    "SR_20Y": 20.0,
    "SR_30Y": 30.0,
}


def fetch_fed_quotes():
    """US Treasury constant maturity yields from the Fed's H.15 release, read from FRED.
    They are par yields on bonds that pay semi-annual coupons."""
    # A month is requested so that weekends and holidays still leave a complete day.
    # FRED expects one start date for each series.
    start_date = str(date.today() - timedelta(days=30))
    start_dates = ",".join([start_date] * len(FED_MATURITIES))
    parameters = {"id": ",".join(FED_MATURITIES), "cosd": start_dates}
    response = requests.get(FED_URL, params=parameters, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    observations = pd.read_csv(io.StringIO(response.text))
    latest = observations.dropna().iloc[-1]

    rows = []
    for series in FED_MATURITIES:
        rows.append({
            "type": "Par yield",
            "maturity_years": FED_MATURITIES[series],
            "rate_percent": latest[series],
        })
    return pd.DataFrame(rows), latest["observation_date"]


def fetch_ecb_quotes():
    """Spot rates on AAA-rated euro area government bonds from the ECB Data Portal.
    The ECB quotes them with continuous compounding, so each is converted to annual compounding."""
    url = ECB_URL + "+".join(ECB_MATURITIES)
    parameters = {"lastNObservations": 1, "format": "csvdata"}
    response = requests.get(url, params=parameters, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    observations = pd.read_csv(io.StringIO(response.text))
    spot_rates = observations.set_index("DATA_TYPE_FM")["OBS_VALUE"]

    rows = []
    for series in ECB_MATURITIES:
        annual_rate = math.exp(spot_rates[series] / 100) - 1
        rows.append({
            "type": "Zero rate",
            "maturity_years": ECB_MATURITIES[series],
            "rate_percent": 100 * annual_rate,
        })
    return pd.DataFrame(rows), observations["TIME_PERIOD"].iloc[0]
