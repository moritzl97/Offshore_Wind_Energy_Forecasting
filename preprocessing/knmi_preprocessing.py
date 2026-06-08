import re
import numpy as np
import pandas as pd
from pathlib import Path


def extract_station_info(path: Path):
    name = path.stem
    name = re.sub(r"\(\d+\)$", "", name).strip()

    match = re.match(r"(.+?)_(\d+)_(\d{4}-\d{4})", name)
    if match:
        station_name = match.group(1).strip()
        station_id = int(match.group(2))
        period = match.group(3)
        return station_name, station_id, period

    return name, np.nan, ""


def read_knmi_file(path: Path) -> pd.DataFrame:
    header_idx = None
    header_line = None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if line.lstrip().startswith("# STN") or line.lstrip().startswith("#STN"):
                header_idx = i
                header_line = line
                break
    if header_idx is None:
        raise ValueError(f"Could not find KNMI data header in {path.name}")

    columns = [c.strip() for c in header_line.lstrip("#").strip().split(",")]
    df = pd.read_csv(
        path,
        skiprows=header_idx + 1,
        names=columns,
        sep=",",
        skipinitialspace=True,
        na_values=["", " ", "   ", "NaN"],
        engine="python"
    )
    df.columns = df.columns.str.strip()

    station_name, station_id, period = extract_station_info(path)
    df["Station"] = station_name
    df["Station_ID"] = station_id
    df["Source_Period"] = period
    df["Source_File"] = path.name
    return df


def parse_timestamps(raw: pd.DataFrame) -> pd.DataFrame:
    raw["YYYYMMDD"] = pd.to_numeric(raw["YYYYMMDD"], errors="coerce")
    raw["HH"] = pd.to_numeric(raw["HH"], errors="coerce")
    raw = raw.dropna(subset=["YYYYMMDD", "HH"]).copy()
    raw["YYYYMMDD"] = raw["YYYYMMDD"].astype(int).astype(str)
    raw["HH"] = raw["HH"].astype(int)
    base_date = pd.to_datetime(raw["YYYYMMDD"], format="%Y%m%d", errors="coerce")
    raw["timestamp"] = base_date + pd.to_timedelta(raw["HH"] - 1, unit="h")
    return raw.dropna(subset=["timestamp"]).copy()


def clean_and_convert_units(knmi: pd.DataFrame) -> pd.DataFrame:
    expected_weather_cols = [
        "DD", "FH", "FF", "FX",
        "T", "T10N", "TD",
        "SQ", "Q",
        "DR", "RH",
        "P", "VV", "N", "U",
        "WW", "IX", "M", "R", "S", "O", "Y"
    ]
    available_cols = [col for col in expected_weather_cols if col in knmi.columns]
    for col in available_cols:
        knmi[col] = pd.to_numeric(knmi[col], errors="coerce")

    if "RH" in knmi.columns:
        knmi["RH"] = knmi["RH"].replace(-1, 0)
    if "SQ" in knmi.columns:
        knmi["SQ"] = knmi["SQ"].replace(-1, 0)
    if "DD" in knmi.columns:
        knmi["DD"] = knmi["DD"].replace(990, np.nan)

    for col in [c for c in ["FH", "FF", "FX"] if c in knmi.columns]:
        knmi[col] = knmi[col] / 10
    for col in [c for c in ["T", "T10N", "TD"] if c in knmi.columns]:
        knmi[col] = knmi[col] / 10
    for col in [c for c in ["P", "RH", "DR", "SQ"] if c in knmi.columns]:
        knmi[col] = knmi[col] / 10

    return knmi


def rename_columns(knmi: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "DD": "wind_direction_deg",         "FH": "wind_speed_ms",
        "FF": "wind_speed_10min_ms",         "FX": "wind_gust_ms",
        "T":  "temperature_c",               "T10N": "min_temp_10cm_c",
        "TD": "dew_point_c",                 "SQ": "sunshine_duration_h",
        "Q":  "global_radiation_j_cm2",      "DR": "precip_duration_h",
        "RH": "precipitation_mm",            "P":  "pressure_hpa",
        "VV": "visibility_code",             "N":  "cloud_cover_octants",
        "U":  "humidity_pct"
    }
    return knmi.rename(columns={k: v for k, v in rename_map.items() if k in knmi.columns})


def add_wind_direction_components(knmi: pd.DataFrame) -> pd.DataFrame:
    if "wind_direction_deg" not in knmi.columns:
        return knmi
    direction = knmi["wind_direction_deg"].copy()
    if "wind_speed_ms" in knmi.columns:
        direction = direction.mask(knmi["wind_speed_ms"] == 0, np.nan)
    radians = np.deg2rad(direction)
    knmi["wind_dir_sin"] = np.sin(radians)
    knmi["wind_dir_cos"] = np.cos(radians)
    return knmi


def interpolate_station(group: pd.DataFrame, continuous_cols, discrete_fill_cols, precip_cols) -> pd.DataFrame:
    group = group.sort_values("timestamp").set_index("timestamp")
    if continuous_cols:
        group[continuous_cols] = group[continuous_cols].interpolate(method="time", limit_direction="both")
    for col in discrete_fill_cols:
        group[col] = group[col].ffill().bfill().round().clip(lower=0, upper=9)
    for col in precip_cols:
        group[col] = group[col].fillna(0)
    return group.reset_index()


def preprocess_knmi_file(path: Path, start_year: int = 2015) -> pd.DataFrame:
    df = read_knmi_file(path)
    df = parse_timestamps(df)
    df = df.drop_duplicates(subset=["Station_ID", "timestamp"], keep="last").copy()
    df = df[df["timestamp"] >= f"{start_year}-01-01"].copy()
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = clean_and_convert_units(df)
    df = rename_columns(df)
    df = add_wind_direction_components(df)

    continuous_cols = [c for c in [
        "wind_speed_ms", "wind_speed_10min_ms", "wind_gust_ms",
        "temperature_c", "min_temp_10cm_c", "dew_point_c",
        "sunshine_duration_h", "global_radiation_j_cm2",
        "pressure_hpa", "humidity_pct", "visibility_code",
        "wind_dir_sin", "wind_dir_cos"
    ] if c in df.columns]
    precip_cols   = [c for c in ["precipitation_mm", "precip_duration_h"] if c in df.columns]
    discrete_cols = [c for c in ["cloud_cover_octants"] if c in df.columns]

    df = interpolate_station(df, continuous_cols, discrete_cols, precip_cols)

    if "wind_dir_sin" in df.columns and "wind_dir_cos" in df.columns:
        angle = np.degrees(np.arctan2(df["wind_dir_sin"], df["wind_dir_cos"]))
        df["wind_direction_interpolated_deg"] = (angle + 360) % 360

    final_cols = [c for c in [
        "timestamp", "Station", "Station_ID", "Source_Period", "Source_File",
        "wind_direction_deg", "wind_direction_interpolated_deg",
        "wind_dir_sin", "wind_dir_cos", "wind_speed_ms", "wind_speed_10min_ms",
        "wind_gust_ms", "temperature_c", "min_temp_10cm_c", "dew_point_c",
        "sunshine_duration_h", "global_radiation_j_cm2", "precip_duration_h",
        "precipitation_mm", "pressure_hpa", "visibility_code",
        "cloud_cover_octants", "humidity_pct"
    ] if c in df.columns]

    return df[final_cols].copy()