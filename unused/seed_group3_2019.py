"""
Seed the ProjectGroup3 / Group3 MongoDB collection with 2019 hourly readings
for the REST API (Azure_functions_REST_API).

Each document is one hourly reading:
    { "Station": <windfarm>, "timestamp": <datetime>,
      "wind_speed_ms": <float|None>, "power_mw": <float|None> }

Stations seeded:
  - the five modelled offshore farms (raw offshore dataset, 2019)
  - "NL_Offshore_National": measured ENTSOE national offshore generation (2019)
    paired with KNMI station 209 hub-height wind speed

Credentials are read from the repo-root .env (MONGO_URI / MONGO_DB /
MONGO_COLLECTION), so nothing secret lives in this file.

Author: Noah Mignola
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MONGO_URI = os.environ["MONGO_URI"]
DB_NAME = os.environ["MONGO_DB"]
COLLECTION_NAME = os.environ["MONGO_COLLECTION"]

YEAR = 2019

OFFSHORE_FILES = {
    "Borssele_12": "Borssele_12.csv",
    "Borssele_34": "Borssele_34.csv",
    "Gemini": "Gemini.csv",
    "Hollandse_Kust_Noord": "Hollandse_Kust_Noord.csv",
    "Hollandse_Kust_Zuid": "Hollandse_Kust_Zuid.csv",
}


def offshore_docs(station, filename):
    path = ROOT / "datasets_raw" / "offshore_dataset" / filename
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["time"])
    df = df[df["timestamp"].dt.year == YEAR]

    docs = []
    for _, r in df.iterrows():
        docs.append({
            "Station": station,
            "timestamp": r["timestamp"].to_pydatetime(),
            "wind_speed_ms": _num(r.get("Scaled_Windspeed_(at_125.5m)")),
            "power_mw": _num(r.get("Power")),
        })
    return docs


def national_docs():
    entsoe = pd.read_csv(ROOT / "datasets" / "entsoe.csv",
                         parse_dates=["Datetime"], index_col="Datetime")
    entsoe = entsoe.loc[str(YEAR)]
    knmi = pd.read_csv(ROOT / "datasets" / "knmi_209_2019.csv",
                       parse_dates=["timestamp"], index_col="timestamp")[["wind_speed_hub_ms"]]
    merged = entsoe.join(knmi, how="left")

    docs = []
    for ts, r in merged.iterrows():
        docs.append({
            "Station": "NL_Offshore_National",
            "timestamp": ts.to_pydatetime(),
            "wind_speed_ms": _num(r.get("wind_speed_hub_ms")),
            "power_mw": _num(r.get("Generation_MW")),
        })
    return docs


def _num(value):
    """Return a float, or None for missing values (Mongo-friendly)."""
    if value is None or pd.isna(value):
        return None
    return float(value)


def main():
    client = MongoClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION_NAME]
    collection.create_index([("Station", ASCENDING), ("timestamp", ASCENDING)],
                            name="station_timestamp")

    stations = list(OFFSHORE_FILES) + ["NL_Offshore_National"]
    # Idempotent: clear any existing readings for these stations before re-seeding.
    collection.delete_many({"Station": {"$in": stations}})

    total = 0
    for station, filename in OFFSHORE_FILES.items():
        docs = offshore_docs(station, filename)
        if docs:
            collection.insert_many(docs)
            total += len(docs)
            print(f"  {station}: inserted {len(docs):,} readings")

    docs = national_docs()
    if docs:
        collection.insert_many(docs)
        total += len(docs)
        print(f"  NL_Offshore_National: inserted {len(docs):,} readings")

    print(f"\nDone. {total:,} documents in '{DB_NAME}.{COLLECTION_NAME}'.")
    print("Windfarms:", sorted(collection.distinct("Station")))
    client.close()


if __name__ == "__main__":
    main()
