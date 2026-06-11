"""
PB1-5: Compile ENTSOE dataset

Combines the yearly "Actual Generation per Production Type" CSV exports from the
ENTSOE Transparency Platform (Netherlands, 2014-2025) into a single clean hourly
time series of Dutch offshore wind generation.

Input:  datasets_raw/entsoe_dataset/AGGREGATED_GENERATION_PER_TYPE_GENERATION_*.csv
Output: datasets/entsoe_nl_offshore_wind.csv  (columns: Datetime, Generation_MW)

Author: Noah Mignola
"""

from pathlib import Path
import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "datasets_raw" / "entsoe_dataset"
OUT_PATH = Path(__file__).resolve().parent.parent / "datasets" / "entsoe_nl_offshore_wind.csv"

PRODUCTION_TYPE = "Wind Offshore"


def load_year_file(path: Path) -> pd.DataFrame:
    """Read one ENTSOE yearly export and return an hourly Wind Offshore series."""
    df = pd.read_csv(path, sep=",", quotechar='"', na_values=["N/A"], low_memory=False)

    df = df[df["Production Type"] == PRODUCTION_TYPE].copy()
    if df.empty:
        return pd.DataFrame(columns=["Datetime", "Generation_MW"]).set_index("Datetime")

    # "MTU (CET/CEST)" looks like "01/01/2020 00:00:00 - 01/01/2020 00:15:00"
    # (DST transition rows additionally have a trailing " (CET)"/" (CEST)" marker)
    start_time = (
        df["MTU (CET/CEST)"]
        .str.split(" - ").str[0]
        .str.replace(r"\s*\(.*?\)", "", regex=True)
        .str.strip()
    )
    df["Datetime"] = pd.to_datetime(start_time, dayfirst=True)

    df["Generation_MW"] = pd.to_numeric(df["Generation (MW)"], errors="coerce")
    df = df[["Datetime", "Generation_MW"]].set_index("Datetime")

    # NL did not have offshore wind capacity before mid-2017; skip empty/zero years
    if df["Generation_MW"].fillna(0).eq(0).all():
        return pd.DataFrame(columns=["Generation_MW"], index=pd.DatetimeIndex([], name="Datetime"))

    # 15-minute MTU resolution -> hourly average
    return df.resample("h").mean()


def compile_entsoe() -> pd.DataFrame:
    files = sorted(RAW_DIR.glob("AGGREGATED_GENERATION_PER_TYPE_GENERATION_*.csv"))
    if not files:
        raise FileNotFoundError(f"No ENTSOE export files found in {RAW_DIR}")

    yearly = [load_year_file(f) for f in files]
    combined = pd.concat(yearly).sort_index()
    combined = combined[~combined.index.duplicated(keep="first")]

    # Drop trailing incomplete days (future/empty data at the end of the export window)
    last_valid = combined["Generation_MW"].last_valid_index()
    if last_valid is not None:
        combined = combined[combined.index.date <= last_valid.date()]

    # Forward-fill single missing hours (e.g. DST transitions)
    combined["Generation_MW"] = combined["Generation_MW"].ffill(limit=1)

    return combined.dropna()


def main():
    df = compile_entsoe()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH)

    print(f"Compiled ENTSOE NL offshore wind generation: {len(df):,} hourly rows")
    print(f"Date range: {df.index.min()} -> {df.index.max()}")
    print(f"Generation (MW): min={df['Generation_MW'].min():.1f}, "
          f"max={df['Generation_MW'].max():.1f}, mean={df['Generation_MW'].mean():.1f}")
    print(f"Saved to {OUT_PATH}")


if __name__ == "__main__":
    main()
