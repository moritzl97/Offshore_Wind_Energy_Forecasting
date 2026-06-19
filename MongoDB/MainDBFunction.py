# add collumns as dictionaries in MongoDB, onetime-function no hardcode, add additional collumns 

import os
import json
import pandas as pd
from pymongo import MongoClient

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER_PATH = os.path.join(BASE_DIR, "datasets_raw", "offshore_dataset")

MONGO_URI  = 'mongodb+srv://25092413_db_user:rZTgL0uPvIArdFen@cluster0.vffsegw.mongodb.net/?appName=Cluster0'
DB_NAME    = 'ProjectGroup3'
client     = MongoClient(MONGO_URI)
db         = client[DB_NAME]
collection = db['Metadata']


FARMS = {
    "Borssele_12"         : "Borssele_12.csv",
    "Borssele_34"         : "Borssele_34.csv",
    "Gemini"              : "Gemini.csv",
    "Hollandse_Kust_Noord": "Hollandse_Kust_Noord.csv",
    "Hollandse_Kust_Zuid" : "Hollandse_Kust_Zuid.csv",
}


def build_and_insert():
    json_path = os.path.join(BASE_DIR, "metadata_wind_farms.json")

    with open(json_path, "r") as f:
        wind_farms_data = json.load(f)

    wind_farms_by_id = {}
    for farm in wind_farms_data["wind_farms"]:
        farm_id = farm.pop("id")
        wind_farms_by_id[farm_id] = farm

    for farm_name, csv_file in FARMS.items():
        df = pd.read_csv(os.path.join(FOLDER_PATH, csv_file), on_bad_lines='skip')

        stats = {}
        for col in df.columns:
            numeric_col = pd.to_numeric(df[col], errors='coerce')
            if numeric_col.notna().any():
                stats[col] = {
                    "max"   : float(numeric_col.max()),
                    "min"   : float(numeric_col.min()),
                    "median": float(numeric_col.median()),
                }

        if farm_name in wind_farms_by_id:
            wind_farms_by_id[farm_name]["statistical_metrics"] = stats
        else:
            wind_farms_by_id[farm_name] = {"statistical_metrics": stats}

        print(f"Processed '{farm_name}' ({len(stats)} columns)")

    document = {
        "metadata": wind_farms_by_id
    }

    collection.insert_one(document)
    print(f"\nInserted combined document with {len(wind_farms_by_id)} location(s)")

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  Wind Farm Metadata to MongoDB")
    print("=" * 50)

    build_and_insert()

    print("\n" + "=" * 50)
    print("  Done")
    print("=" * 50)
    client.close()