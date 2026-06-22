import requests
import pandas as pd
from datetime import datetime, timedelta

ENTSOE_WEB_URL = "https://transparency.entsoe.eu/generation/actual/perType/generation/load"

HEADERS = {
    "accept": "application/json",
    "content-type": "application/json; charset=utf-8",
    "cookie": "uu.app.bpl=0",
    "origin": "https://transparency.entsoe.eu",
}

# PSR production type codes (subset relevant to this project)
PRODUCTION_TYPE_WIND_OFFSHORE = "B18"


def fetch_entsoe_generation(area_code: str, date_from: str, date_to: str, timezone: str = "CET") -> dict:
    """
    Fetch actual generation per production type from the ENTSOE Transparency
    Platform's public website endpoint (no security token required).

    area_code: e.g. "BZN|10YNL----------L" for the Netherlands bidding zone.
    date_from, date_to: ISO date strings, e.g. "2026-06-17".
    Returns the raw parsed JSON response.
    """
    payload = {
        "dateTimeRange": {
            "from": f"{date_from}T22:00:00.000Z",
            "to": f"{date_to}T22:00:00.000Z",
        },
        "areaList": [area_code],
        "timeZone": timezone,
        "sorterList": [],
        "filterMap": {},
    }

    response = requests.post(ENTSOE_WEB_URL, headers=HEADERS, json=payload)
    response.raise_for_status()
    return response.json()


def extract_production_type_series(data: dict, production_type: str, resample_hourly: bool = False) -> pd.Series:
    """
    Extract a single production type's generation series from the raw
    fetch_entsoe_generation() response, indexed by timestamp (UTC).

    If resample_hourly is True, the native 15-minute series is averaged
    into hourly buckets to match a typically hourly Timeseries collection.
    """
    for instance in data.get("instanceList", []):
        if instance["businessDimensionMap"].get("PRODUCTION_TYPE") != production_type:
            continue

        for period in instance["curveData"]["periodList"]:
            start = datetime.fromisoformat(period["timeInterval"]["from"].replace("Z", "+00:00"))
            resolution_minutes = 15  # PT15M

            timestamps = []
            values = []
            for idx_str, point in sorted(period["pointMap"].items(), key=lambda kv: int(kv[0])):
                idx = int(idx_str)
                ts = start + timedelta(minutes=resolution_minutes * idx)

                value = point[0]
                if isinstance(value, dict):
                    # missing/not-yet-available point, e.g. {"alt": "-"} or {"alt": "n/e"}
                    continue

                timestamps.append(ts)
                values.append(float(value))

            series = pd.Series(values, index=pd.DatetimeIndex(timestamps), name=production_type)

            if resample_hourly:
                series = series.resample("h").mean()

            return series

    raise ValueError(f"Production type '{production_type}' not found in response")


def insert_entsoe_offshore_wind_actual(area_code: str, date_from: str, date_to: str,
                                        mongo_uri: str, mongo_db: str = "wind_farm",
                                        collection_name: str = "Timeseries") -> None:
    """
    Fetch actual offshore wind generation (B19) for the given area and date
    range from the ENTSOE web endpoint, resample to hourly, convert from UTC
    to Europe/Amsterdam local time (matching the rest of the Timeseries
    collection), and upsert it into actual_mw on the "TOTAL" pseudo-farm
    documents.
    """
    from pymongo import MongoClient, UpdateOne

    data = fetch_entsoe_generation(area_code, date_from, date_to)
    series = extract_production_type_series(data, PRODUCTION_TYPE_WIND_OFFSHORE, resample_hourly=True)

    # series index is UTC (tz-aware); convert to local Dutch time to match
    # the rest of the collection (KNMI/Open-Meteo data is stored in
    # Europe/Amsterdam local time, not UTC).
    series.index = series.index.tz_convert("Europe/Amsterdam").tz_localize(None)

    client = MongoClient(mongo_uri)
    collection = client[mongo_db][collection_name]

    operations = [
        UpdateOne(
            {"timestamp": ts.to_pydatetime(), "farm_id": "TOTAL"},
            {"$set": {"actual_mw": float(value)}},
            upsert=True
        )
        for ts, value in series.items()
        if pd.notna(value)
    ]

    if not operations:
        print("No data points to insert")
        return

    result = collection.bulk_write(operations, ordered=False)
    print(f"TOTAL actual_mw: upserted={result.upserted_count}, modified={result.modified_count}")


if __name__ == "__main__":
    data = fetch_entsoe_generation(
        area_code="BZN|10YNL----------L",
        date_from="2026-06-20",
        date_to="2026-06-21",
    )

    offshore_wind = extract_production_type_series(data, PRODUCTION_TYPE_WIND_OFFSHORE)
    print(offshore_wind)