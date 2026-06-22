from pathlib import Path
import joblib
import pandas as pd

from models.feature_engineering.weather_data_feature_engineering import engineer_features

FARMS = {
    "Borssele_12",
    "Borssele_34",
    "Gemini",
    "Hollandse_Kust_Noord",
    "Hollandse_Kust_Zuid",
}

MODELS_DIR = Path(__file__).resolve().parent / "trained_models"

def predict_power(wind_farm_name, features_dict):
    if wind_farm_name not in FARMS:
        raise ValueError(f"Unknown wind farm: {wind_farm_name}")

    root = Path(__file__).resolve().parents[2]

    model_path = MODELS_DIR / f"neural_network_{wind_farm_name}.pkl"

    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    saved = joblib.load(model_path)

    model = saved["model"]
    feature_columns = saved["features"]

    row = {}
    for col in feature_columns:
        if col not in features_dict:
            raise ValueError(f"Missing required feature: {col}")
        row[col] = features_dict[col]

    X = pd.DataFrame([row])

    prediction = float(model.predict(X)[0])

    return max(0.0, prediction)


def predict_power_neural_network(wind_farm_name, weather_df):
    """
    Full pipeline:
    raw weather data -> feature engineering -> neural network prediction
    Returns predictions for every row in weather_df (not just the latest).
    """
    features_df = engineer_features(wind_farm_name, weather_df, return_all_rows=True)
    predictions = []
    for _, row in features_df.iterrows():
        features_dict = row.to_dict()
        predictions.append(predict_power(wind_farm_name, features_dict))
    return predictions

if __name__ == "__main__":
    timestamps = pd.date_range(end="2019-06-15 12:00:00", periods=25, freq="h")
    speeds = [
        8.0, 9.0, 9.5, 10.0, 10.5, 10.0,
        9.5, 9.0, 8.5, 8.0, 7.5, 7.0,
        7.5, 8.0, 8.5, 9.0, 9.5, 10.0,
        10.5, 11.0, 10.5, 10.0, 9.5, 10.0,
        10.0,  # current hour
    ]

    weather_df = pd.DataFrame({
        "timestamp": timestamps,
        "wind_speed_ms": speeds,
        "wind_direction_deg": [220.0] * 25,
        "pressure_hpa": [1015.0] * 25,
        "temperature_c": [18.5] * 25,
    })

    prediction = predict_power_neural_network("Gemini", weather_df)
    print(f"Predicted power output for Gemini: {prediction:.2f} MW")