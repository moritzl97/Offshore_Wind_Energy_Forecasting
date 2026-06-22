"""
Backfill the last 48 hours of:
  1. Open-Meteo weather + model predictions (per farm + TOTAL)
  2. ENTSOE actual generation (TOTAL)

Run this once locally (or as a one-off Azure Function invocation) to fill
gaps in the Timeseries collection, e.g. after downtime or a missed schedule.

Requires the same environment variables as function_app.py:
  MONGO_URI, MONGO_DB (optional), MONGO_COLLECTION_TIMESERIES (optional)
"""

import logging
import os
from datetime import datetime, timedelta

import pandas as pd
import requests
from pymongo import MongoClient, UpdateOne

from models.predict_knowledge_driven_model import predict_power_knowledge_model
from models.predict_power_neural import predict_power_neural_network
from models.predict_decision_tree import predict_power_decision_tree
from entsoe_web_fetcher import insert_entsoe_offshore_wind_actual

from dotenv import load_dotenv

load_dotenv("../.env")
MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB    = os.environ["MONGO_DB"]
COLLECTION = os.environ["MONGO_COLLECTION_TIMESERIES"]


FARMS = {
    "Borssele_12":          {"lat": 51.75, "lon": 3.25},
    "Borssele_34":          {"lat": 51.72, "lon": 3.22},
    "Gemini":               {"lat": 54.03, "lon": 5.95},
    "Hollandse_Kust_Zuid":  {"lat": 52.35, "lon": 4.25},
    "Hollandse_Kust_Noord": {"lat": 52.75, "lon": 4.50},
}

BACKFILL_HOURS = 48


def fetch_openmeteo_past(lat: float, lon: float, past_hours: int = 48) -> pd.DataFrame:
    """
    Fetch hourly historical weather for the last `past_hours` hours using
    Open-Meteo's forecast endpoint with the past_days parameter (covers
    recent history without needing the separate archive API).
    """
    past_days = max(1, -(-past_hours // 24))  # round up to whole days

    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "wind_speed_10m,wind_direction_10m,surface_pressure,temperature_2m",
            "wind_speed_unit": "ms",
            "timezone": "Europe/Amsterdam",
            "past_days": past_days,
            "forecast_days": 1,  # we'll trim anything beyond "now" below
        },
        timeout=15,
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

    now = pd.Timestamp.now().floor("h")
    cutoff_start = now - pd.Timedelta(hours=past_hours)
    df = df[(df["timestamp"] >= cutoff_start) & (df["timestamp"] <= now)].reset_index(drop=True)
    return df


def get_collection():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB][COLLECTION]


def backfill_weather_and_predictions():
    logging.info(f"Backfilling weather + predictions for the last {BACKFILL_HOURS}h")

    collection = get_collection()
    totals_by_timestamp = {}

    for farm_id, info in FARMS.items():
        try:
            df = fetch_openmeteo_past(info["lat"], info["lon"], past_hours=BACKFILL_HOURS)

            if df.empty:
                logging.warning(f"{farm_id}: no historical rows returned, skipping")
                continue

            predicted_knowledge_model = predict_power_knowledge_model(df["wind_speed_ms"].values, farm_id)
            predicted_decision_tree = predict_power_decision_tree(farm_id, df)
            predicted_neural_network = predict_power_neural_network(farm_id, df)

            operations = []
            for i, (_, row) in enumerate(df.iterrows()):
                ts = row["timestamp"].to_pydatetime()

                knowledge_val = float(predicted_knowledge_model[i])
                tree_val = float(predicted_decision_tree[i])
                nn_val = float(predicted_neural_network[i])

                operations.append(
                    UpdateOne(
                        {"timestamp": ts, "farm_id": farm_id},
                        {"$set": {
                            "weather_data": {
                                "wind_speed_ms": float(row["wind_speed_ms"]),
                                "wind_direction_deg": float(row["wind_direction_deg"]),
                                "pressure_hpa": float(row["pressure_hpa"]),
                                "temperature_c": float(row["temperature_c"]),
                            },
                            "predictions.knowledge_based_mw": knowledge_val,
                            "predictions.decision_tree_mw": tree_val,
                            "predictions.neural_network_mw": nn_val,
                        }},
                        upsert=True
                    )
                )

                if ts not in totals_by_timestamp:
                    totals_by_timestamp[ts] = {"knowledge_based_mw": 0.0, "decision_tree_mw": 0.0, "neural_network_mw": 0.0}
                totals_by_timestamp[ts]["knowledge_based_mw"] += knowledge_val
                totals_by_timestamp[ts]["decision_tree_mw"] += tree_val
                totals_by_timestamp[ts]["neural_network_mw"] += nn_val

            result = collection.bulk_write(operations, ordered=False)
            logging.info(f"{farm_id}: upserted={result.upserted_count}, modified={result.modified_count}")

        except Exception as e:
            logging.error(f"Failed to backfill {farm_id}: {e}")
            continue

    if totals_by_timestamp:
        total_operations = [
            UpdateOne(
                {"timestamp": ts, "farm_id": "TOTAL"},
                {"$set": {
                    "predictions.knowledge_based_mw": totals["knowledge_based_mw"],
                    "predictions.decision_tree_mw": totals["decision_tree_mw"],
                    "predictions.neural_network_mw": totals["neural_network_mw"],
                }},
                upsert=True
            )
            for ts, totals in totals_by_timestamp.items()
        ]
        total_result = collection.bulk_write(total_operations, ordered=False)
        logging.info(f"TOTAL predictions: upserted={total_result.upserted_count}, modified={total_result.modified_count}")

    logging.info("Weather + predictions backfill complete")


def backfill_entsoe_actuals():
    logging.info(f"Backfilling ENTSOE actuals for the last {BACKFILL_HOURS}h")
    AREA_CODE_NL = "BZN|10YNL----------L"

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=(BACKFILL_HOURS // 24) + 1)

    try:
        insert_entsoe_offshore_wind_actual(
            area_code=AREA_CODE_NL,
            date_from=start_date.isoformat(),
            date_to=today.isoformat(),
            mongo_uri=MONGO_URI,
            mongo_db=MONGO_DB,
            collection_name=COLLECTION,
        )
    except Exception as e:
        logging.error(f"Failed to backfill ENTSOE actuals: {e}")

    logging.info("ENTSOE actuals backfill complete")


if __name__ == "__main__":
    backfill_weather_and_predictions()
    backfill_entsoe_actuals()