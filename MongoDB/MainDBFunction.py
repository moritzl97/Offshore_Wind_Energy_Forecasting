# add collumns as dictionaries in MongoDB, onetime-function no hardcode, add additional collumns 

import os
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
    "Borssele_12"         : "Borssele_(Phase_1,2).csv",
    "Borssele_34"         : "Borssele_(Phase_3,4).csv",
    "Gemini"              : "Gemini.csv",
    "Hollandse_Kust_Noord": "Hollandse_Kust_Noord.csv",
    "Hollandse_Kust_Zuid" : "Hollandse_Kust_Zuid.csv",
}


def build_and_insert(farm_name, csv_file):
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

    document = {
        "location": farm_name,
        "stats"   : stats,
    }

    collection.insert_one(document)
    print(f"Inserted metadata for '{farm_name}' ({len(stats)} columns)")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  Wind Farm Metadata to MongoDB")
    print("=" * 50)

    for farm_name, csv_file in FARMS.items():
        build_and_insert(farm_name, csv_file)

    print("\n" + "=" * 50)
    print("  Done")
    print("=" * 50)
    client.close()