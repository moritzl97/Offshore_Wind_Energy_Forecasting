import logging
import os
from datetime import datetime, timedelta

import azure.functions as func
from pymongo import MongoClient, UpdateOne

from open_meteo_fetcher import fetch_openmeteo_forecast
from knowledge_driven_model import predict_power_knowledge_model
from predict_power_neural import predict_power_neural_network
from predict_decision_tree import predict_power_decision_tree
from entsoe_web_fetcher import insert_entsoe_offshore_wind_actual

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
    schedule="0 2 * * * *",
    run_on_startup=True
)
def hourly_weather_forecast_and_power_predictor(timer: func.TimerRequest) -> None:
    logging.info("Hourly Open-Meteo forecast ingestion started")

    collection = get_collection()
    totals_by_timestamp = {}  # {ts: {"knowledge_based_mw": x, "decision_tree_mw": y, "neural_network_mw": z}}

    for farm_id, info in FARMS.items():
        try:
            df = fetch_openmeteo_forecast(info["lat"], info["lon"], forecast_hours=24)

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
            logging.error(f"Failed to fetch/insert forecast for {farm_id}: {e}")
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
        logging.info(f"TOTAL: upserted={total_result.upserted_count}, modified={total_result.modified_count}")

    logging.info("Hourly Open-Meteo forecast ingestion complete")

@app.timer_trigger(
    arg_name="timer",
    schedule="0 2 * * * *",  # every hour, on the hour
    run_on_startup=True
)
def hourly_entsoe_actual_ingestion(timer: func.TimerRequest) -> None:
    logging.info("Hourly ENTSOE actual generation ingestion started")
    AREA_CODE_NL = "BZN|10YNL----------L"

    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)

    try:
        insert_entsoe_offshore_wind_actual(
            area_code=AREA_CODE_NL,
            date_from=yesterday.isoformat(),
            date_to=today.isoformat(),
            mongo_uri=MONGO_URI,
            mongo_db=MONGO_DB,
            collection_name=COLLECTION,
        )
    except Exception as e:
        logging.error(f"Failed to fetch/insert ENTSOE actual generation: {e}")

    logging.info("Hourly ENTSOE actual generation ingestion complete")