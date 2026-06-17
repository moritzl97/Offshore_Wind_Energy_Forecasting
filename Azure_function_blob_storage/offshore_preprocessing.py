import io
import pandas as pd
from pathlib import Path


def preprocess_wind_farm_content(raw_csv: str, farm_name: str, capacity_mw=None) -> pd.DataFrame:
    """
    Core function. Takes raw CSV text content, works for both
    local files and blob storage.
    """
    df = pd.read_csv(io.StringIO(raw_csv))

    drop_cols = ["u100", "v100", "fsr", "Unnamed: 0"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])
    df = df.drop(columns=[c for c in df.columns if c.startswith("Power_of_")])

    df.columns = ["Scaled_Windspeed" if c.startswith("Scaled_Windspeed") else c for c in df.columns]

    df = df.set_index("time")
    df.index = pd.to_datetime(df.index)

    df["Station"] = farm_name
    if capacity_mw:
        df.loc[df["Power"] > capacity_mw, "Power"] = capacity_mw

    return df


def preprocess_wind_farm(path: Path, farm_name: str, capacity_mw: float) -> pd.DataFrame:
    """Local-file wrapper, used by preprocess_all_raw_datasets.py."""
    with open(path, "r", encoding="utf-8") as f:
        raw_csv = f.read()
    return preprocess_wind_farm_content(raw_csv, farm_name, capacity_mw)