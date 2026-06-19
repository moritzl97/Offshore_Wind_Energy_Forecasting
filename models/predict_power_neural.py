from pathlib import Path
import joblib
import pandas as pd

FARMS = {
    "Borssele_12",
    "Borssele_34",
    "Gemini",
    "Hollandse_Kust_Noord",
    "Hollandse_Kust_Zuid",
}

def predict_power(wind_farm_name, features_dict):
    if wind_farm_name not in FARMS:
        raise ValueError(
            f"Unknown wind farm: {wind_farm_name}"
        )

    root = Path(__file__).resolve().parents[2]

    model_path = (
        root
        / "models"
        / "saved"
        / f"neural_network_{wind_farm_name}.pkl"
    )

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model file not found: {model_path}"
        )

    saved = joblib.load(model_path)

    model = saved["model"]
    feature_columns = saved["features"]

    row = {}

    for col in feature_columns:
        if col not in features_dict:
            raise ValueError(
                f"Missing required feature: {col}"
            )
        row[col] = features_dict[col]

    X = pd.DataFrame([row])

    prediction = float(model.predict(X)[0])

    return max(0.0, prediction)

import numpy as np


def create_features_from_weather(weather_df):
    """
    Takes raw weather data and creates the feature dictionary needed by predict_power().

    Required input columns:
    - timestamp
    - wind_speed_ms
    - wind_direction_deg
    - pressure_hpa
    - temperature_c

    Returns:
    - features_dict for the latest timestamp
    """

    df = weather_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").set_index("timestamp")

    # Basic engineered features
    df["wind_speed_hub_ms"] = df["wind_speed_ms"]
    df["wind_power_density"] = 0.5 * 1.225 * (df["wind_speed_hub_ms"] ** 3)

    # Wind direction as sin/cos
    direction_rad = np.deg2rad(df["wind_direction_deg"])
    df["wind_dir_sin"] = np.sin(direction_rad)
    df["wind_dir_cos"] = np.cos(direction_rad)

    # Lag features
    df["wind_speed_lag_1h"] = df["wind_speed_hub_ms"].shift(1)
    df["wind_speed_lag_6h"] = df["wind_speed_hub_ms"].shift(6)
    df["wind_speed_lag_24h"] = df["wind_speed_hub_ms"].shift(24)

    # Rolling features
    df["wind_speed_roll_3h"] = df["wind_speed_hub_ms"].rolling(3).mean()
    df["wind_speed_roll_24h"] = df["wind_speed_hub_ms"].rolling(24).mean()

    # Time features
    df["hour_sin"] = np.sin(2 * np.pi * df.index.hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df.index.hour / 24)
    df["month_sin"] = np.sin(2 * np.pi * df.index.month / 12)
    df["month_cos"] = np.cos(2 * np.pi * df.index.month / 12)

    latest = df.iloc[-1]

    features_dict = {
        "wind_speed_hub_ms": latest["wind_speed_hub_ms"],
        "wind_power_density": latest["wind_power_density"],
        "wind_dir_sin": latest["wind_dir_sin"],
        "wind_dir_cos": latest["wind_dir_cos"],
        "wind_speed_lag_1h": latest["wind_speed_lag_1h"],
        "wind_speed_lag_6h": latest["wind_speed_lag_6h"],
        "wind_speed_lag_24h": latest["wind_speed_lag_24h"],
        "wind_speed_roll_3h": latest["wind_speed_roll_3h"],
        "wind_speed_roll_24h": latest["wind_speed_roll_24h"],
        "pressure_hpa": latest["pressure_hpa"],
        "temperature_c": latest["temperature_c"],
        "month_sin": latest["month_sin"],
        "month_cos": latest["month_cos"],
        "hour_sin": latest["hour_sin"],
        "hour_cos": latest["hour_cos"],
    }

    return features_dict


def predict_power_from_weather(wind_farm_name, weather_df):
    """
    Full pipeline:
    raw weather data -> feature engineering -> neural network prediction
    """

    features_dict = create_features_from_weather(weather_df)
    prediction = predict_power(wind_farm_name, features_dict)

    return prediction