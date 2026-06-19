import numpy as np
import pandas as pd
import warnings

# Hub heights per farm (from metadata_wind_farms.json)
HUB_HEIGHTS = {
    "Borssele_12":          116.5,
    "Borssele_34":          100.0,
    "Gemini":               120.0,
    "Hollandse_Kust_Zuid":  125.5,
    "Hollandse_Kust_Noord": 125.5,
}

ALPHA = 0.11         # offshore wind power law exponent, used for hub height extrapolation
AIR_DENSITY = 1.225  # kg/m^3, standard air density at sea level, used for wind power density

FEATURE_COLUMNS = [
    "wind_speed_hub_ms",
    "wind_power_density",
    "wind_dir_sin",
    "wind_dir_cos",
    "wind_speed_lag_1h",
    "wind_speed_lag_6h",
    "wind_speed_lag_24h",
    "wind_speed_roll_3h",
    "wind_speed_roll_24h",
    "pressure_hpa",
    "temperature_c",
    "month_sin",
    "month_cos",
    "hour_sin",
    "hour_cos",
]


def engineer_features(wind_farm_name: str, weather_df: pd.DataFrame, return_all_rows: bool = False):
    """
    Build the 15 features used by the decision tree and neural network
    models from a dataframe of hourly weather data.

    Parameters
    ----------
    wind_farm_name : str
        One of: 'Borssele_12', 'Borssele_34', 'Gemini',
        'Hollandse_Kust_Zuid', 'Hollandse_Kust_Noord'
    weather_df : pd.DataFrame
        Must contain columns: timestamp, wind_speed_ms, wind_direction_deg,
        pressure_hpa, temperature_c, at hourly resolution. Should contain
        at least 24 rows ending at the timestamp(s) you want features for,
        since lag/rolling features look back up to 24 hours.
    return_all_rows : bool, default False
        If True, returns a dataframe with features for every input row.
        If False (default), returns a dict with features for only the
        most recent timestamp.

    Returns
    -------
    dict (most recent row's features) or pd.DataFrame (all rows),
    depending on return_all_rows.
    """
    if wind_farm_name not in HUB_HEIGHTS:
        raise ValueError(
            f"Unknown wind farm '{wind_farm_name}'. "
            f"Available farms: {list(HUB_HEIGHTS.keys())}"
        )

    scaling_factor = (HUB_HEIGHTS[wind_farm_name] / 10) ** ALPHA

    df = weather_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").set_index("timestamp")

    if len(df) < 24:
        warnings.warn(
            f"Only {len(df)} rows provided; lag/rolling features requiring "
            f"24 hours of history will be NaN for the most recent rows."
        )

    df["wind_speed_hub_ms"] = df["wind_speed_ms"] * scaling_factor
    df["wind_power_density"] = 0.5 * AIR_DENSITY * (df["wind_speed_hub_ms"] ** 3)

    direction_rad = np.deg2rad(df["wind_direction_deg"])
    df["wind_dir_sin"] = np.sin(direction_rad)
    df["wind_dir_cos"] = np.cos(direction_rad)

    df["wind_speed_lag_1h"] = df["wind_speed_hub_ms"].shift(1)
    df["wind_speed_lag_6h"] = df["wind_speed_hub_ms"].shift(6)
    df["wind_speed_lag_24h"] = df["wind_speed_hub_ms"].shift(24)

    df["wind_speed_roll_3h"] = df["wind_speed_hub_ms"].rolling(3).mean()
    df["wind_speed_roll_24h"] = df["wind_speed_hub_ms"].rolling(24).mean()

    df["hour_sin"] = np.sin(2 * np.pi * df.index.hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df.index.hour / 24)
    df["month_sin"] = np.sin(2 * np.pi * df.index.month / 12)
    df["month_cos"] = np.cos(2 * np.pi * df.index.month / 12)

    if return_all_rows:
        return df[FEATURE_COLUMNS]

    latest = df.iloc[-1]
    return {col: latest[col] for col in FEATURE_COLUMNS}


if __name__ == "__main__":
    timestamps = pd.date_range(end="2019-06-15 12:00:00", periods=25, freq="h")
    speeds = [
        8.0, 9.0, 9.5, 10.0, 10.5, 10.0,
        9.5, 9.0, 8.5, 8.0, 7.5, 7.0,
        7.5, 8.0, 8.5, 9.0, 9.5, 10.0,
        10.5, 11.0, 10.5, 10.0, 9.5, 10.0,
        10.0,
    ]
    df = pd.DataFrame({
        "timestamp": timestamps,
        "wind_speed_ms": speeds,
        "wind_direction_deg": [220.0] * 25,
        "pressure_hpa": [1015.0] * 25,
        "temperature_c": [18.5] * 25,
    })

    features = engineer_features("Gemini", df)

    print("Engineered features for Gemini:")
    for k, v in features.items():
        print(f"  {k:<22} {v:.4f}")