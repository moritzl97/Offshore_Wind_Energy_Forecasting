import logging
import os
from datetime import datetime

import azure.functions as func
from pymongo import MongoClient, UpdateOne

from open_meteo_fetcher import fetch_openmeteo_forecast
from knowledge_driven_model import predict_power_knowledge_model

app = func.FunctionApp()

MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB", "wind_farm")
COLLECTION = os.environ.get("MONGO_COLLECTION_TIMESERIES", "Timeseries")

FARMS = {
    "Borssele_12":          {"lat": 51.75, "lon": 3.25},
    "Borssele_34":          {"lat": 51.72, "lon": 3.22},
    "Gemini":               {"lat": 54.03, "lon": 5.95},
    "Hollandse_Kust_Zuid":  {"lat": 52.35, "lon": 4.25},
    "Hollandse_Kust_Noord": {"lat": 52.75, "lon": 4.50},
}


def get_collection():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB][COLLECTION]


@app.timer_trigger(
    arg_name="timer",
    schedule="0 0 * * * *",  # every hour, on the hour
    run_on_startup=True
)
def hourly_weather_forecast_and_power_predictor(timer: func.TimerRequest) -> None:
    logging.info("Hourly Open-Meteo forecast ingestion started")

    collection = get_collection()
    totals_by_timestamp = {}

    for farm_id, info in FARMS.items():
        try:
            df = fetch_openmeteo_forecast(info["lat"], info["lon"], forecast_hours=24)

            predicted_knowledge_model = predict_power_knowledge_model(df["wind_speed_ms"].values, farm_id)

            operations = []
            for i, (_, row) in enumerate(df.iterrows()):
                ts = row["timestamp"].to_pydatetime()
                predicted_knowledge_model_float = float(predicted_knowledge_model[i])

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
                            "predictions.knowledge_based_mw": predicted_knowledge_model_float,
                        }},
                        upsert=True
                    )
                )
                totals_by_timestamp[ts] = totals_by_timestamp.get(ts, 0) + predicted_knowledge_model_float

            result = collection.bulk_write(operations, ordered=False)
            logging.info(f"{farm_id}: upserted={result.upserted_count}, modified={result.modified_count}")

        except Exception as e:
            logging.error(f"Failed to fetch/insert forecast for {farm_id}: {e}")
            continue

    # write the TOTAL documents
    if totals_by_timestamp:
        total_operations = [
            UpdateOne(
                {"timestamp": ts, "farm_id": "TOTAL"},
                {"$set": {"predictions.knowledge_based_mw": total_power}},
                upsert=True
            )
            for ts, total_power in totals_by_timestamp.items()
        ]
        total_result = collection.bulk_write(total_operations, ordered=False)
        logging.info(f"TOTAL: upserted={total_result.upserted_count}, modified={total_result.modified_count}")

    logging.info("Hourly Open-Meteo forecast ingestion complete")