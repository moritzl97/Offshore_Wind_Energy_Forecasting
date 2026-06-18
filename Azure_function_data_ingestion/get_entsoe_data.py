import logging
import os
import pandas as pd
from datetime import datetime, timedelta
from entsoe import EntsoePandasClient

ENTSOE_API_KEY = os.environ.get("ENTSOE_API_KEY")


def fetch_entsoe_day(date: datetime = None) -> pd.DataFrame:
    """
    Fetch hourly offshore wind generation for the Netherlands for a given date.
    Defaults to yesterday to ensure complete data is available.
    """
    if date is None:
        date = datetime.utcnow() - timedelta(days=1)

    logging.info(f"Fetching ENTSOE data for {date.date()}")

    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)
    start = pd.Timestamp(date.strftime("%Y%m%d"), tz="Europe/Amsterdam")
    end   = start + pd.Timedelta(days=1)

    series = client.query_generation(
        country_code="NL",
        start=start,
        end=end,
        psr_type="B19"  # B19 = offshore wind
    )

    df = series.reset_index()
    df.columns = ["timestamp", "actual_power_mw"]
    df["timestamp"] = df["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None)
    df = df.resample("h", on="timestamp").mean().reset_index()

    logging.info(f"Fetched {len(df)} ENTSOE records")
    return df