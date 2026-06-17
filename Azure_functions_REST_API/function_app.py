import logging
import json
import os
from datetime import datetime

from dotenv import load_dotenv

import azure.functions as func
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError


# Helper function
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def _json(payload, status_code=200):
    return func.HttpResponse(
        json.dumps(payload, cls=DateTimeEncoder),
        mimetype="application/json",
        status_code=status_code,
    )


def _parse_dt(value):
    """Parse an ISO date/datetime query string into a datetime, or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# App & DB setup
load_dotenv("../.env")

app = func.FunctionApp()

MONGO_URI = os.environ["MONGO_URI"]
DB_NAME = os.environ["MONGO_DB"]
COLLECTION_NAME = os.environ["MONGO_COLLECTION"]

# Create a single client for the whole app and make sure the index that the
# windfarm/time-range queries rely on exists. The compound index on
# (Station, timestamp) supports both the "distinct Station" lookups and the
# range scans done by the timeseries endpoint.
_client = MongoClient(MONGO_URI)
_collection = _client[DB_NAME][COLLECTION_NAME]
try:
    _collection.create_index([("Station", ASCENDING), ("timestamp", ASCENDING)],
                             name="station_timestamp")
except PyMongoError as exc:  # don't crash app startup if Atlas is briefly unreachable
    logging.warning("Could not ensure index: %s", exc)


def get_collection():
    return _collection


# REST API
@app.route(route="windfarms", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_turbines(req: func.HttpRequest) -> func.HttpResponse:
    """Return a list of unique windfarm names."""
    try:
        collection = get_collection()
        stations = sorted(collection.distinct("Station"))
        return _json({"windfarms": stations, "count": len(stations)})
    except PyMongoError as e:
        return func.HttpResponse(str(e), status_code=500)


@app.route(route="windfarms/{windfarm_name}/timeseries", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_timeseries(req: func.HttpRequest) -> func.HttpResponse:
    """
    Return the timeseries (wind speed and power) for a specific windfarm.

    Optional query parameters:
      ?start=YYYY-MM-DD   only readings on/after this date
      ?end=YYYY-MM-DD     only readings on/before this date
      ?limit=N            cap the number of readings returned (default 1000)
    """
    windfarm_name = req.route_params.get("windfarm_name")
    start = _parse_dt(req.params.get("start"))
    end = _parse_dt(req.params.get("end"))
    try:
        limit = int(req.params.get("limit", 1000))
    except ValueError:
        return func.HttpResponse("'limit' must be an integer", status_code=400)

    query: dict = {"Station": windfarm_name}
    if start or end:
        query["timestamp"] = {}
        if start:
            query["timestamp"]["$gte"] = start
        if end:
            query["timestamp"]["$lte"] = end

    try:
        collection = get_collection()
        cursor = (
            collection.find(query, {"_id": 0})
            .sort("timestamp", ASCENDING)
            .limit(limit)
        )
        records = list(cursor)
        return _json({
            "windfarm": windfarm_name,
            "count": len(records),
            "readings": records,
        })
    except PyMongoError as e:
        return func.HttpResponse(str(e), status_code=500)


@app.route(route="windfarms/{windfarm_name}/metadata", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_metadata(req: func.HttpRequest) -> func.HttpResponse:
    """
    Return summary metadata for a specific windfarm, computed from its readings:
    number of readings, the covered time range, the observed rated capacity
    (max power), the mean power, and the resulting capacity factor.
    """
    windfarm_name = req.route_params.get("windfarm_name")

    pipeline = [
        {"$match": {"Station": windfarm_name}},
        {"$group": {
            "_id": "$Station",
            "readings": {"$sum": 1},
            "start": {"$min": "$timestamp"},
            "end": {"$max": "$timestamp"},
            "max_power_mw": {"$max": "$power_mw"},
            "mean_power_mw": {"$avg": "$power_mw"},
            "mean_wind_speed_ms": {"$avg": "$wind_speed_ms"},
        }},
    ]

    try:
        collection = get_collection()
        result = list(collection.aggregate(pipeline))
        if not result:
            return func.HttpResponse(
                f"No data found for windfarm '{windfarm_name}'", status_code=404
            )
        doc = result[0]
        capacity = doc.get("max_power_mw")
        mean_power = doc.get("mean_power_mw")
        capacity_factor = (
            round(mean_power / capacity, 3) if capacity else None
        )
        return _json({
            "windfarm": windfarm_name,
            "readings": doc["readings"],
            "start": doc["start"],
            "end": doc["end"],
            "rated_capacity_mw": round(capacity, 1) if capacity is not None else None,
            "mean_power_mw": round(mean_power, 1) if mean_power is not None else None,
            "mean_wind_speed_ms": (
                round(doc["mean_wind_speed_ms"], 2)
                if doc.get("mean_wind_speed_ms") is not None else None
            ),
            "capacity_factor": capacity_factor,
        })
    except PyMongoError as e:
        return func.HttpResponse(str(e), status_code=500)


@app.route(route="timeseries", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def post_reading(req: func.HttpRequest) -> func.HttpResponse:
    """
    Insert a single reading.
    Expected JSON body:
    {
      "Station": "NL_Offshore_National",
      "timestamp": "2026-06-15T00:00:00",
      "wind_speed_ms": 8.5,
      "power_mw": 612.0
    }
    """
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)

    if not body.get("Station") or not body.get("timestamp"):
        return func.HttpResponse(
            "'Station' and 'timestamp' are required fields", status_code=400
        )

    ts = body.get("timestamp")
    if isinstance(ts, str):
        parsed = _parse_dt(ts)
        if parsed is None:
            return func.HttpResponse(
                "'timestamp' must be an ISO date/datetime string", status_code=400
            )
        body["timestamp"] = parsed

    try:
        collection = get_collection()
        collection.insert_one(body)
        body.pop("_id", None)
        return _json({"inserted": body}, status_code=201)
    except PyMongoError as e:
        return func.HttpResponse(str(e), status_code=500)
