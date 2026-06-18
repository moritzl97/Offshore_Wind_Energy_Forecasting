import pandas as pd
from dotenv import load_dotenv
import os
import numpy as np
from pymongo import MongoClient, UpdateOne
from models.knowledge_driven_model import predict_power_knowledge_model

load_dotenv("../.env")
MONGO_URI  = os.environ["MONGO_URI"]
DB_NAME    = os.environ["MONGO_DB"]
COLLECTION = os.environ["MONGO_COLLECTION_TIMESERIES"]

farm_station_map = {
    "Borssele_12":          "Vlissingen",
    "Borssele_34":          "Vlissingen",
    "Gemini":               "Hoorn",
    "Hollandse_Kust_Zuid":  "Hoek_van_Holland",
    "Hollandse_Kust_Noord": "Hoek_van_Holland",
}

def insert_knmi_weather_2026(datasets_folder: str = "./datasets"):
    client = MongoClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION]

    for farm_id, station_name in farm_station_map.items():
        csv_path = f"{datasets_folder}/knmi_{station_name}.csv"

        try:
            df = pd.read_csv(csv_path, index_col="timestamp", parse_dates=True)
        except FileNotFoundError:
            print(f"Skipping {farm_id}: file not found at {csv_path}")
            continue

        df = df[df.index.year == 2026]

        if df.empty:
            print(f"No 2026 data for {farm_id} (station {station_name})")
            continue

        operations = [
            UpdateOne(
                {"timestamp": ts.to_pydatetime(), "farm_id": farm_id},
                {
                    "$set": {
                        "weather": {
                            "wind_speed_ms":     float(row["wind_speed_ms"]) if pd.notna(row["wind_speed_ms"]) else None,
                            "wind_direction_deg": float(row["wind_direction_deg"]) if pd.notna(row["wind_direction_deg"]) else None,
                            "pressure_hpa":       float(row["pressure_hpa"]) if pd.notna(row["pressure_hpa"]) else None,
                            "temperature_c":      float(row["temperature_c"]) if pd.notna(row["temperature_c"]) else None,
                        }
                    },
                    "$unset": {"wind_speed_ms": ""}
                },
                upsert=True
            )
            for ts, row in df.iterrows()
        ]

        result = collection.bulk_write(operations, ordered=False)
        print(f"{farm_id} ({station_name}): upserted {result.upserted_count}, modified {result.modified_count}")

def apply_knowledge_model_to_db():
    client = MongoClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION]

    # only documents that have a wind speed but belong to a real farm (not TOTAL)
    cursor = collection.find(
        {
            "weather.wind_speed_ms": {"$exists": True, "$ne": None},
            "farm_id": {"$ne": "TOTAL"}
        },
        {"_id": 1, "farm_id": 1, "weather.wind_speed_ms": 1}
    )

    operations = []
    skipped_farms = set()

    for doc in cursor:
        farm_id = doc["farm_id"]
        wind_speed = doc["weather"]["wind_speed_ms"]

        try:
            predicted = predict_power_knowledge_model(wind_speed, farm_id)
            predicted_value = float(np.atleast_1d(predicted)[0])
        except ValueError:
            skipped_farms.add(farm_id)
            continue

        operations.append(
            UpdateOne(
                {"_id": doc["_id"]},
                {"$set": {"predictions.knowledge_based_mw": predicted_value}}
            )
        )

    if skipped_farms:
        print(f"Skipped farms not in fitted_params.json: {skipped_farms}")

    if not operations:
        print("No documents to update")
        return

    # bulk_write in batches to avoid huge single requests
    batch_size = 1000
    total_modified = 0
    for i in range(0, len(operations), batch_size):
        batch = operations[i:i + batch_size]
        result = collection.bulk_write(batch, ordered=False)
        total_modified += result.modified_count

    print(f"Updated {total_modified} documents with knowledge_based_mw predictions")

def calculate_knowledge_based_total():
    client = MongoClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION]

    pipeline = [
        {"$match": {
            "farm_id": {"$ne": "TOTAL"},
            "predictions.knowledge_based_mw": {"$exists": True, "$ne": None}
        }},
        {"$group": {
            "_id": "$timestamp",
            "total_knowledge_based_mw": {"$sum": "$predictions.knowledge_based_mw"}
        }}
    ]

    results = list(collection.aggregate(pipeline))

    if not results:
        print("No knowledge_based_mw predictions found to total")
        return

    operations = [
        UpdateOne(
            {"timestamp": row["_id"], "farm_id": "TOTAL"},
            {"$set": {"predictions.knowledge_based_mw": row["total_knowledge_based_mw"]}},
            upsert=True
        )
        for row in results
    ]

    batch_size = 1000
    total_upserted = 0
    total_modified = 0
    for i in range(0, len(operations), batch_size):
        batch = operations[i:i + batch_size]
        result = collection.bulk_write(batch, ordered=False)
        total_upserted += result.upserted_count
        total_modified += result.modified_count

    print(f"TOTAL documents: upserted {total_upserted}, modified {total_modified}")

if __name__ == "__main__":
    insert_knmi_weather_2026()
    apply_knowledge_model_to_db()
    calculate_knowledge_based_total()