import numpy as np
import pandas as pd
from datetime import datetime

# Hub heights per farm (from metadata_wind_farms.json)
HUB_HEIGHTS = {
    "Borssele_12":          116.5,
    "Borssele_34":          100.0,
    "Gemini":               120.0,
    "Hollandse_Kust_Zuid":  125.5,
    "Hollandse_Kust_Noord": 125.5,
}

ALPHA = 0.11  # offshore power law exponent


def engineer_features(wind_farm_name, raw_data):
    """
    Transform raw KNMI weather data into the 15 features the
    Decision Tree model expects.

    Parameters
    ----------
    wind_farm_name : str
        Name of the wind farm. Must be one of:
        'Borssele_12', 'Borssele_34', 'Gemini',
        'Hollandse_Kust_Zuid', 'Hollandse_Kust_Noord'

    raw_data : dict
        Dictionary containing raw KNMI measurements and short history.
        Required keys:
          - timestamp (datetime or string)
          - wind_speed_ms (current 10m wind speed in m/s)
          - wind_direction_deg (current wind direction in degrees)
          - pressure_hpa
          - temperature_c
          - wind_speed_history (list of last 24 hourly wind speeds in m/s,
                                oldest first, newest last)

    Returns
    -------
    dict
        Dictionary with all 15 features ready to feed into predict_power().
    """

    # Validate farm
    if wind_farm_name not in HUB_HEIGHTS:
        raise ValueError(f"Unknown wind farm: {wind_farm_name}")
    
    hub_height = HUB_HEIGHTS[wind_farm_name]
    
    # Parse timestamp
    ts = raw_data["timestamp"]
    if isinstance(ts, str):
        ts = pd.to_datetime(ts)
    
    # Wind speed history (last 24 hours, in m/s at 10m)
    history = raw_data["wind_speed_history"]
    if len(history) < 24:
        raise ValueError(f"wind_speed_history must contain at least 24 values, got {len(history)}")
    
    # ── Feature 1: Wind direction sin/cos ──
    wind_dir_rad = np.radians(raw_data["wind_direction_deg"])
    wind_dir_sin = np.sin(wind_dir_rad)
    wind_dir_cos = np.cos(wind_dir_rad)
    
    # ── Feature 2: Hub height extrapolation ──
    scaling_factor = (hub_height / 10) ** ALPHA
    wind_speed_hub_ms = raw_data["wind_speed_ms"] * scaling_factor
    
    # Also scale the historical wind speeds to hub height
    history_hub = [v * scaling_factor for v in history]
    
    # ── Feature 3: Wind power density ──
    wind_power_density = wind_speed_hub_ms ** 3
    
    # ── Feature 4: Lag features ──
    # history_hub is oldest → newest, so:
    # lag_1h  = 1 hour ago = second to last
    # lag_24h = 24 hours ago = first element
    wind_speed_lag_1h  = history_hub[-2]
    wind_speed_lag_6h  = history_hub[-7]
    wind_speed_lag_24h = history_hub[-24]
    
    # ── Feature 5: Rolling averages ──
    wind_speed_roll_3h  = np.mean(history_hub[-3:])
    wind_speed_roll_24h = np.mean(history_hub[-24:])
    
    # ── Feature 6: Time features ──
    hour  = ts.hour
    month = ts.month
    
    hour_sin  = np.sin(2 * np.pi * hour  / 24)
    hour_cos  = np.cos(2 * np.pi * hour  / 24)
    month_sin = np.sin(2 * np.pi * month / 12)
    month_cos = np.cos(2 * np.pi * month / 12)
    
    # ── Build feature dictionary ──
    features = {
        "wind_speed_hub_ms":   wind_speed_hub_ms,
        "wind_power_density":  wind_power_density,
        "wind_dir_sin":        wind_dir_sin,
        "wind_dir_cos":        wind_dir_cos,
        "wind_speed_lag_1h":   wind_speed_lag_1h,
        "wind_speed_lag_6h":   wind_speed_lag_6h,
        "wind_speed_lag_24h":  wind_speed_lag_24h,
        "wind_speed_roll_3h":  wind_speed_roll_3h,
        "wind_speed_roll_24h": wind_speed_roll_24h,
        "pressure_hpa":        raw_data["pressure_hpa"],
        "temperature_c":       raw_data["temperature_c"],
        "month_sin":           month_sin,
        "month_cos":           month_cos,
        "hour_sin":            hour_sin,
        "hour_cos":            hour_cos,
    }
    
    return features


# Example usage / test
if __name__ == "__main__":
    
    raw_input = {
        "timestamp":          "2019-06-15 12:00:00",
        "wind_speed_ms":      10.0,
        "wind_direction_deg": 220.0,
        "pressure_hpa":       1015.0,
        "temperature_c":      18.5,
        "wind_speed_history": [
            8.0, 9.0, 9.5, 10.0, 10.5, 10.0,
            9.5, 9.0, 8.5, 8.0, 7.5, 7.0,
            7.5, 8.0, 8.5, 9.0, 9.5, 10.0,
            10.5, 11.0, 10.5, 10.0, 9.5, 10.0
        ]
    }
    
    features = engineer_features("Gemini", raw_input)
    
    print("Engineered features for Gemini:")
    for k, v in features.items():
        print(f"  {k:<25} {v:.4f}")
    
    # Add parent folder to path so we can import predict
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from models.predict_decision_tree import predict_power
    
    prediction = predict_power("Gemini", features)
    print(f"\nPredicted power: {prediction:.2f} MW")