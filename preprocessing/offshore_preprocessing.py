import pandas as pd
import json
from pathlib import Path

def preprocess_wind_farm(path: Path, farm_name: str, capacity_mw: float) -> pd.DataFrame:
    df = pd.read_csv(path)

    # drop unused columns
    drop_cols = ["u100", "v100", "fsr", "Unnamed: 0"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])
    df = df.drop(columns=[c for c in df.columns if c.startswith("Power_of_")])

    # rename scaled windspeed
    df.columns = ["Scaled_Windspeed" if c.startswith("Scaled_Windspeed") else c for c in df.columns]

    df = df.set_index("time")
    df.index = pd.to_datetime(df.index)

    df["Station"] = farm_name

    # cap power at installed capacity
    df.loc[df["Power"] > capacity_mw, "Power"] = capacity_mw

    return df