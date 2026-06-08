from pathlib import Path
import re
import numpy as np
import pandas as pd


def extract_station_info(path: Path):
    name = path.stem
    name = re.sub(r"\(\d+\)$", "", name).strip() # remove endings like (1)

    match = re.match(r"(.+?)_(\d+)_(\d{4}-\d{4})", name)
    if match:
        station_name = match.group(1).strip()
        station_id = int(match.group(2))
        period = match.group(3)
        return station_name, station_id, period

    # Fallback if filename format is different
    return name, np.nan, ""


def read_knmi_file(path: Path) -> pd.DataFrame:
    """Read one KNMI hourly txt file into a clean dataframe with metadata columns."""
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


def KNMI():
    # Find project root and KNMI raw data folder automatically
    cwd = Path.cwd()

    possible_data_dirs = [
        cwd.parent / "datasets_raw" / "KNMI", # when notebook is inside preprocessing/
        cwd / "datasets_raw" / "KNMI",        # when notebook is run from project root
        cwd / "KNMI",                         # when notebook is inside datasets_raw/
        cwd,                                  # when notebook is directly inside the txt folder
    ]

    DATA_DIR = None
    for path in possible_data_dirs:
        if path.exists() and list(path.glob("*.txt")):
            DATA_DIR = path
            break

    if DATA_DIR is None:
        raise FileNotFoundError(
            "Could not find KNMI .txt files. Expected them in ../datasets_raw/KNMI or datasets_raw/KNMI. "
            f"Current working directory is: {cwd}"
        )

    PROJECT_ROOT = DATA_DIR.parent.parent if DATA_DIR.name == "KNMI" else cwd
    OUTPUT_DIR = PROJECT_ROOT / "datasets"
    STATION_OUTPUT_DIR = OUTPUT_DIR / "KNMI_by_station_2015plus"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATION_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(DATA_DIR.glob("*.txt"))

    # Load all files
    raw_parts = []
    for file in files:
        df_part = read_knmi_file(file)
        raw_parts.append(df_part)

    raw = pd.concat(raw_parts, ignore_index=True)

    # Create timestamps
    # Convert date/hour columns
    raw["YYYYMMDD"] = pd.to_numeric(raw["YYYYMMDD"], errors="coerce")
    raw["HH"] = pd.to_numeric(raw["HH"], errors="coerce")

    # Drop rows that do not have a valid date or hour
    raw = raw.dropna(subset=["YYYYMMDD", "HH"]).copy()
    raw["YYYYMMDD"] = raw["YYYYMMDD"].astype(int).astype(str)
    raw["HH"] = raw["HH"].astype(int)

    # Create timestamp
    base_date = pd.to_datetime(raw["YYYYMMDD"], format="%Y%m%d", errors="coerce")
    raw["timestamp"] = base_date + pd.to_timedelta(raw["HH"] - 1, unit="h")

    # Drop invalid timestamps
    raw = raw.dropna(subset=["timestamp"]).copy()

    # Sort and combine split files belonging to the same station
    raw = raw.sort_values(["Station_ID", "Station", "timestamp"]).reset_index(drop=True)

    # Remove duplicate station-timestamp rows if overlapping files exist
    raw = raw.drop_duplicates(subset=["Station_ID", "timestamp"], keep="last").copy()

    # Trim to 2015
    knmi = raw[raw["timestamp"] >= "2015-01-01"].copy()
    knmi = knmi.sort_values(["Station_ID", "timestamp"]).reset_index(drop=True)

    # Columns expected in KNMI hourly weather data
    expected_weather_cols = [
        "DD", "FH", "FF", "FX",             # wind direction, wind speed, gusts
        "T", "T10N", "TD",                  # temperature variables
        "SQ", "Q",                          # sunshine and radiation
        "DR", "RH",                         # precipitation duration and amount
        "P", "VV", "N", "U",                # pressure, visibility, cloud cover, humidity
        "WW", "IX", "M", "R", "S", "O", "Y" # weather codes / indicators
    ]

    available_cols = [col for col in expected_weather_cols if col in knmi.columns]

    # Convert weather columns to numeric
    for col in available_cols:
        knmi[col] = pd.to_numeric(knmi[col], errors="coerce")

    # Clean special values
    if "RH" in knmi.columns:
        knmi["RH"] = knmi["RH"].replace(-1, 0)
    if "SQ" in knmi.columns:
        knmi["SQ"] = knmi["SQ"].replace(-1, 0)
    if "DD" in knmi.columns:
        knmi["DD"] = knmi["DD"].replace(990, np.nan)

    # Convert units
    for col in [c for c in ["FH", "FF", "FX"] if c in knmi.columns]:
        knmi[col] = knmi[col] / 10
    for col in [c for c in ["T", "T10N", "TD"] if c in knmi.columns]:
        knmi[col] = knmi[col] / 10
    for col in [c for c in ["P", "RH", "DR", "SQ"] if c in knmi.columns]:
        knmi[col] = knmi[col] / 10

    # Rename important columns to clearer names while keeping original KNMI codes useful
    rename_map = {
        "DD": "wind_direction_deg", "FH": "wind_speed_ms",
        "FF": "wind_speed_10min_ms", "FX": "wind_gust_ms",
        "T": "temperature_c", "T10N": "min_temp_10cm_c",
        "TD": "dew_point_c", "SQ": "sunshine_duration_h",
        "Q": "global_radiation_j_cm2", "DR": "precip_duration_h",
        "RH": "precipitation_mm", "P": "pressure_hpa",
        "VV": "visibility_code", "N": "cloud_cover_octants",
        "U": "humidity_pct"
    }

    knmi = knmi.rename(columns={k: v for k, v in rename_map.items() if k in knmi.columns})

    # Create circular wind direction components before interpolation
    if "wind_direction_deg" in knmi.columns:
        direction = knmi["wind_direction_deg"].copy()

        # If wind speed is 0, direction is not meaningful
        if "wind_speed_ms" in knmi.columns:
            direction = direction.mask(knmi["wind_speed_ms"] == 0, np.nan)

        radians = np.deg2rad(direction)
        knmi["wind_dir_sin"] = np.sin(radians)
        knmi["wind_dir_cos"] = np.cos(radians)

    # Variables suitable for time interpolation+
    continuous_cols = [c for c in [
        "wind_speed_ms", "wind_speed_10min_ms", "wind_gust_ms",
        "temperature_c", "min_temp_10cm_c", "dew_point_c",
        "sunshine_duration_h", "global_radiation_j_cm2",
        "pressure_hpa", "humidity_pct", "visibility_code",
        "wind_dir_sin", "wind_dir_cos"
    ] if c in knmi.columns]

    # Variables that should not be smoothly interpolated
    precip_cols = [c for c in ["precipitation_mm", "precip_duration_h"] if c in knmi.columns]
    discrete_fill_cols = [c for c in ["cloud_cover_octants"] if c in knmi.columns]

    def interpolate_group(group):
        group = group.sort_values("timestamp").copy()
        group = group.set_index("timestamp")

        # Time-based interpolation within each station
        if continuous_cols:
            group[continuous_cols] = group[continuous_cols].interpolate(method="time", limit_direction="both")

        # Cloud cover is discrete, so forward/backward fill then round
        for col in discrete_fill_cols:
            group[col] = group[col].ffill().bfill().round().clip(lower=0, upper=9)

        # Precipitation: after trace values are cleaned, missing is treated as 0
        for col in precip_cols:
            group[col] = group[col].fillna(0)

        return group.reset_index()

    # Safer than groupby().apply(): avoids Station_ID becoming an index level and causing KeyError/ambiguity
    processed_groups = []
    for station_id, group in knmi.groupby("Station_ID", sort=False):
        processed_groups.append(interpolate_group(group))

    # Make sure Station_ID and timestamp are normal columns before sorting
    knmi_preprocessed = pd.concat(processed_groups, ignore_index=True)

    # Make sure Station_ID and timestamp are normal columns before sorting
    knmi_preprocessed = knmi_preprocessed.reset_index(drop=True)
    knmi_preprocessed["timestamp"] = pd.to_datetime(knmi_preprocessed["timestamp"])
    knmi_preprocessed = knmi_preprocessed.sort_values(["Station_ID", "timestamp"]).reset_index(drop=True)

    # Reconstruct interpolated wind direction from sine/cosine components
    if "wind_dir_sin" in knmi_preprocessed.columns and "wind_dir_cos" in knmi_preprocessed.columns:
        angle = np.degrees(np.arctan2(knmi_preprocessed["wind_dir_sin"], knmi_preprocessed["wind_dir_cos"]))
        knmi_preprocessed["wind_direction_interpolated_deg"] = (angle + 360) % 360

    # Select final columns
    final_cols = [c for c in [
        "timestamp", "Station", "Station_ID", "Source_Period", "Source_File",
        "wind_direction_deg", "wind_direction_interpolated_deg",
        "wind_dir_sin", "wind_dir_cos", "wind_speed_ms", "wind_speed_10min_ms",
        "wind_gust_ms", "temperature_c", "min_temp_10cm_c", "dew_point_c",
        "sunshine_duration_h", "global_radiation_j_cm2", "precip_duration_h",
        "precipitation_mm", "pressure_hpa", "visibility_code",
        "cloud_cover_octants", "humidity_pct"
    ] if c in knmi_preprocessed.columns]

    final_knmi = knmi_preprocessed[final_cols].copy()

    # Save combined
    final_knmi.to_csv(OUTPUT_DIR / "knmi_combined_2015plus_preprocessed.csv", index=False)

    # Save per station
    for station, group in final_knmi.groupby("Station"):
        safe_station = re.sub(r"[^A-Za-z0-9_]+", "_", station).strip("_")
        group.to_csv(STATION_OUTPUT_DIR / f"knmi_{safe_station}_2015plus_preprocessed.csv", index=False)

    return final_knmi