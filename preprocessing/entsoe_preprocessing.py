import io
import pandas as pd
from pathlib import Path


def preprocess_entsoe_content(raw_csv: str) -> pd.DataFrame:
    """
    Core function. Processes a single ENTSOE CSV's raw content
    into an hourly offshore wind generation time series.
    """
    df = pd.read_csv(io.StringIO(raw_csv), sep=",", quotechar='"', na_values=["N/A"], low_memory=False)

    df = df[df["Production Type"] == "Wind Offshore"]

    df["Datetime"] = pd.to_datetime(
        df["MTU (CET/CEST)"]
        .str.split(" - ").str[0]
        .str.replace(r"\(.*?\)", "", regex=True)
        .str.strip(),
        dayfirst=True
    )

    df = df[["Datetime", "Generation (MW)"]]
    df.rename(columns={"Generation (MW)": "Generation_MW"}, inplace=True)
    df["Generation_MW"] = pd.to_numeric(df["Generation_MW"], errors="coerce")

    if (df["Generation_MW"].fillna(0) == 0).all():
        return pd.DataFrame(columns=["Generation_MW"])

    df = df.set_index("Datetime")
    df = df.resample("h").mean()
    df = df.ffill(limit=1)

    return df


def ENTSO_timeseries(path_raw: Path):
    """Local-folder wrapper. Concatenates multiple daily/monthly ENTSOE exports."""
    raw_files = sorted(path_raw.glob("*.csv"))
    df_full_timeseries = pd.DataFrame()

    for file in raw_files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                raw_csv = f.read()
            df = preprocess_entsoe_content(raw_csv)
        except Exception as e:
            print(f"FAILED: {file.name} -> {e}")
            continue

        if df.empty:
            print(f"File skipped because its empty: {file}")
            continue

        df_full_timeseries = pd.concat([df_full_timeseries, df])

    last_valid = df_full_timeseries["Generation_MW"].last_valid_index()
    if last_valid:
        last_valid_day = last_valid.date()
        df_full_timeseries = df_full_timeseries[df_full_timeseries.index.date < last_valid_day]

    df_full_timeseries = df_full_timeseries.ffill(limit=1)

    return df_full_timeseries