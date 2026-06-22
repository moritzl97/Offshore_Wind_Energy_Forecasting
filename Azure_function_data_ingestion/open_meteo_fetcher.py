import logging
import requests
import pandas as pd

def fetch_openmeteo_forecast(lat: float, lon: float, forecast_hours: int = 24) -> pd.DataFrame:
    """
    Fetch hourly forecast weather for a location for the next `forecast_hours` hours.
    """
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "wind_speed_10m,wind_direction_10m,surface_pressure,temperature_2m",
            "wind_speed_unit": "ms",
            "timezone": "Europe/Amsterdam",
            "forecast_hours": forecast_hours,
        },
        timeout=15
    )
    response.raise_for_status()
    data = response.json()

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(data["hourly"]["time"]),
        "wind_speed_ms": data["hourly"]["wind_speed_10m"],
        "wind_direction_deg": data["hourly"]["wind_direction_10m"],
        "pressure_hpa": data["hourly"]["surface_pressure"],
        "temperature_c": data["hourly"]["temperature_2m"],
    })
    return df

if __name__ == "__main__":
    lat, lon = 51.75, 3.25  # Borssele_12
    df = fetch_openmeteo_forecast(lat, lon, forecast_hours=24)
    print(df)