import joblib
import numpy as np
import pandas as pd
from pathlib import Path

from models.feature_engineering.weather_data_feature_engineering import engineer_features

# Path to the saved models folder
MODELS_DIR = Path(__file__).resolve().parent / "trained_models"

# Features the model expects (must match training order)
FEATURES = [
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

# Hub heights per farm (from metadata)
HUB_HEIGHTS = {
    "Borssele_12":          116.5,
    "Borssele_34":          100.0,
    "Gemini":               120.0,
    "Hollandse_Kust_Zuid":  125.5,
    "Hollandse_Kust_Noord": 125.5,
}


def predict_power(wind_farm_name, features_dict):
    """
    Predict offshore wind power output for a given wind farm.

    Parameters
    ----------
    wind_farm_name : str
        Name of the wind farm. Must be one of:
        'Borssele_12', 'Borssele_34', 'Gemini',
        'Hollandse_Kust_Zuid', 'Hollandse_Kust_Noord'

    features_dict : dict
        Dictionary containing all 15 required features.
        Keys must match the FEATURES list.

    Returns
    -------
    float
        Predicted power output in MW.
    """

    model_path = MODELS_DIR / f"decision_tree_{wind_farm_name}.pkl"
    if not model_path.exists():
        raise FileNotFoundError(f"No saved model for {wind_farm_name} at {model_path}")

    model = joblib.load(model_path)

    try:
        X = pd.DataFrame([[features_dict[f] for f in FEATURES]], columns=FEATURES)
    except KeyError as e:
        raise KeyError(f"Missing required feature: {e}")

    prediction = model.predict(X)[0]
    return max(0.0, float(prediction))


def predict_power_decision_tree(wind_farm_name, weather_df):
    """
    Full pipeline:
    raw weather data -> feature engineering -> decision tree prediction
    Returns predictions for every row in weather_df (not just the latest).
    """
    features_df = engineer_features(wind_farm_name, weather_df, return_all_rows=True)
    predictions = []
    for _, row in features_df.iterrows():
        features_dict = row.to_dict()
        predictions.append(predict_power(wind_farm_name, features_dict))
    return predictions


# Example usage
if __name__ == "__main__":

    example_features = {
        "wind_speed_hub_ms":   12.5,
        "wind_power_density":  1953.125,
        "wind_dir_sin":        -0.64,
        "wind_dir_cos":        -0.77,
        "wind_speed_lag_1h":   12.0,
        "wind_speed_lag_6h":   10.5,
        "wind_speed_lag_24h":  8.0,
        "wind_speed_roll_3h":  12.2,
        "wind_speed_roll_24h": 10.0,
        "pressure_hpa":        1015.0,
        "temperature_c":       8.5,
        "month_sin":           0.5,
        "month_cos":           0.87,
        "hour_sin":            0.0,
        "hour_cos":            1.0,
    }

    prediction = predict_power("Gemini", example_features)
    print(f"Predicted power output for Gemini: {prediction:.2f} MW")