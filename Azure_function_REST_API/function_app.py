import logging
import json
import os
from datetime import datetime

import azure.functions as func
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError

# Load local MONGO_URI / MONGO_DB / MONGO_COLLECTION
# available. Safe to call even if the file is missing.

app = func.FunctionApp()

REQUIRED_ENV = ("MONGO_URI", "MONGO_DB", "MONGO_COLLECTION_METADATA", "MONGO_COLLECTION_TIMESERIES")
MAX_LIMIT = 5000
DEFAULT_LIMIT = 1000

# A single client is reused across invocations. It is created lazily on first
# use so that a missing config or an unreachable database returns a clean error
# response instead of crashing the worker at import time.
_client = None

# CORS headers so browser-based stakeholders (e.g. the project website) can call
# the API directly.
_CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


class ConfigError(Exception):
    """Raised when required configuration is missing."""


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
        headers=_CORS,
    )


def _error(message, status_code):
    return func.HttpResponse(
        json.dumps({"error": message}),
        mimetype="application/json",
        status_code=status_code,
        headers=_CORS,
    )


def _get_client():
    """Return the shared MongoClient, creating it lazily on first use."""
    global _client

    missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        raise ConfigError(
            "Missing required configuration: " + ", ".join(missing)
            + ". Set them in the .env file at the project root."
        )

    if _client is None:
        # serverSelectionTimeoutMS keeps the API from hanging if Atlas is down;
        # it surfaces a clean 503 within a few seconds instead.
        _client = MongoClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=5000)

    return _client


def get_timeseries_collection():
    """Return the Timeseries collection, ensuring its index exists on first use."""
    client = _get_client()
    collection = client[os.environ["MONGO_DB"]][os.environ["MONGO_COLLECTION_TIMESERIES"]]
    return collection


def get_metadata_collection():
    """Return the Metadata collection."""
    client = _get_client()
    return client[os.environ["MONGO_DB"]][os.environ["MONGO_COLLECTION_METADATA"]]


def _handle(fn, req):
    """Run an endpoint body with uniform, never-crashing error handling."""
    try:
        return fn(req)
    except ConfigError as e:
        logging.error("Config error: %s", e)
        return _error(str(e), 503)
    except PyMongoError as e:
        logging.error("Database error: %s", e)
        return _error("Database error: " + str(e), 503)
    except Exception as e:  # last-resort guard so the API never returns an unhandled crash
        logging.exception("Unexpected error")
        return _error("Unexpected server error: " + str(e), 500)

def _parse_dt(value):
    """Parse an ISO date/datetime string. Returns (datetime|None, ok)."""
    if value is None or value == "":
        return None, True
    try:
        return datetime.fromisoformat(value), True
    except (ValueError, TypeError):
        return None, False


def _parse_limit(value):
    """Parse and clamp the limit parameter. Returns (limit|None, error|None)."""
    if value is None:
        return DEFAULT_LIMIT, None
    try:
        limit = int(value)
    except (ValueError, TypeError):
        return None, "'limit' must be an integer"
    if limit <= 0:
        return None, "'limit' must be a positive integer"
    return min(limit, MAX_LIMIT), None


# REST API
@app.route(route="windfarms", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_windfarm_names(req: func.HttpRequest) -> func.HttpResponse:
    """Return a list of unique windfarm ids present in the Timeseries collection, excluding TOTAL."""
    def body(req):
        collection = get_timeseries_collection()
        farms = sorted(collection.distinct("farm_id"))
        return _json({"windfarms": farms, "count": len(farms)})
    return _handle(body, req)


@app.route(route="windfarms/{windfarm_name}/timeseries", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_timeseries(req: func.HttpRequest) -> func.HttpResponse:
    """
    Return the timeseries (weather inputs, predictions, actual power) for a
    specific windfarm, or "TOTAL" for the aggregated national total.

    Optional query parameters:
      ?start=YYYY-MM-DD   only readings on/after this date
      ?end=YYYY-MM-DD     only readings on/before this date
      ?limit=N            cap the number of readings (default 1000, max 5000)
    """

    def body(req):
        windfarm_name = req.route_params.get("windfarm_name")
        if not windfarm_name:
            return _error("windfarm name is required", 400)

        start, ok_start = _parse_dt(req.params.get("start"))
        if not ok_start:
            return _error("'start' must be an ISO date, e.g. 2026-01-01", 400)
        end, ok_end = _parse_dt(req.params.get("end"))
        if not ok_end:
            return _error("'end' must be an ISO date, e.g. 2026-12-31", 400)

        limit, limit_err = _parse_limit(req.params.get("limit"))
        if limit_err:
            return _error(limit_err, 400)

        query = {"farm_id": windfarm_name}
        if start or end:
            query["timestamp"] = {}
            if start:
                query["timestamp"]["$gte"] = start
            if end:
                query["timestamp"]["$lte"] = end

        collection = get_timeseries_collection()
        cursor = collection.find(query, {"_id": 0}).sort("timestamp", ASCENDING).limit(limit)
        records = list(cursor)
        return _json({
            "windfarm": windfarm_name,
            "count": len(records),
            "limit": limit,
            "readings": records,
        })

    return _handle(body, req)


@app.route(route="windfarms/{windfarm_name}/weather", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_weather(req: func.HttpRequest) -> func.HttpResponse:
    """
    Return only the weather inputs (timestamp + nested weather object) for a
    specific windfarm, or "TOTAL" for the aggregated national total.

    Optional query parameters:
      ?start=YYYY-MM-DD   only readings on/after this date
      ?end=YYYY-MM-DD     only readings on/before this date
      ?limit=N            cap the number of readings (default 1000, max 5000)
    """

    def body(req):
        windfarm_name = req.route_params.get("windfarm_name")
        if not windfarm_name:
            return _error("windfarm name is required", 400)

        start, ok_start = _parse_dt(req.params.get("start"))
        if not ok_start:
            return _error("'start' must be an ISO date, e.g. 2026-01-01", 400)
        end, ok_end = _parse_dt(req.params.get("end"))
        if not ok_end:
            return _error("'end' must be an ISO date, e.g. 2026-12-31", 400)

        limit, limit_err = _parse_limit(req.params.get("limit"))
        if limit_err:
            return _error(limit_err, 400)

        query = {"farm_id": windfarm_name}
        if start or end:
            query["timestamp"] = {}
            if start:
                query["timestamp"]["$gte"] = start
            if end:
                query["timestamp"]["$lte"] = end

        collection = get_timeseries_collection()
        cursor = (
            collection.find(query, {"_id": 0, "timestamp": 1, "weather": 1})
            .sort("timestamp", ASCENDING)
            .limit(limit)
        )
        records = list(cursor)
        return _json({
            "windfarm": windfarm_name,
            "count": len(records),
            "limit": limit,
            "readings": records,
        })

    return _handle(body, req)

@app.route(route="windfarms/{windfarm_name}/predictions", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_predictions(req: func.HttpRequest) -> func.HttpResponse:
    """
    Return only the model predictions and actual power (timestamp + nested
    predictions object + actual_mw) for a specific windfarm, or "TOTAL" for
    the aggregated national total.

    Optional query parameters:
      ?start=YYYY-MM-DD   only readings on/after this date
      ?end=YYYY-MM-DD     only readings on/before this date
      ?limit=N            cap the number of readings (default 1000, max 5000)
      ?model=NAME          only return this model's prediction (e.g. knowledge_based_mw),
                            instead of the full predictions object
    """
    def body(req):
        windfarm_name = req.route_params.get("windfarm_name")
        if not windfarm_name:
            return _error("windfarm name is required", 400)

        start, ok_start = _parse_dt(req.params.get("start"))
        if not ok_start:
            return _error("'start' must be an ISO date, e.g. 2026-01-01", 400)
        end, ok_end = _parse_dt(req.params.get("end"))
        if not ok_end:
            return _error("'end' must be an ISO date, e.g. 2026-12-31", 400)

        limit, limit_err = _parse_limit(req.params.get("limit"))
        if limit_err:
            return _error(limit_err, 400)

        model = req.params.get("model")

        query = {"farm_id": windfarm_name}
        if start or end:
            query["timestamp"] = {}
            if start:
                query["timestamp"]["$gte"] = start
            if end:
                query["timestamp"]["$lte"] = end

        projection = {"_id": 0, "timestamp": 1, "actual_mw": 1}
        if model:
            projection[f"predictions.{model}"] = 1
        else:
            projection["predictions"] = 1

        collection = get_timeseries_collection()
        cursor = (
            collection.find(query, projection)
            .sort("timestamp", ASCENDING)
            .limit(limit)
        )
        records = list(cursor)
        return _json({
            "windfarm": windfarm_name,
            "model": model,
            "count": len(records),
            "limit": limit,
            "readings": records,
        })
    return _handle(body, req)

@app.route(route="windfarms/{windfarm_name}/metadata", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_metadata(req: func.HttpRequest) -> func.HttpResponse:
    """
    Return the stored metadata for a specific windfarm.

    The Metadata collection holds a single document shaped like
    {"Metadata": {"<farm_id>": {<per-column stats>}, ...}}. This endpoint
    fetches that document and hands back the block for the requested windfarm
    as JSON -- no computation, just whatever is stored.
    """

    def body(req):
        windfarm_name = req.route_params.get("windfarm_name")
        if not windfarm_name:
            return _error("windfarm name is required", 400)

        collection = get_metadata_collection()
        doc = collection.find_one({}, {"_id": 0})
        if not doc or "Metadata" not in doc:
            return _error("No metadata document found", 404)

        farms = doc["Metadata"]
        if windfarm_name not in farms:
            return _error(f"No metadata found for windfarm '{windfarm_name}'", 404)

        return _json({
            "windfarm": windfarm_name,
            "metadata": farms[windfarm_name],
        })

    return _handle(body, req)


@app.route(route="timeseries", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def post_reading(req: func.HttpRequest) -> func.HttpResponse:
    """
    Insert a single reading.
    Expected JSON body:
    {
      "farm_id": "Borssele_12",
      "timestamp": "2026-06-15T00:00:00",
      "weather": {"wind_speed_ms": 8.5},
      "predictions": {"knowledge_based_mw": 612.0}
    }
    """

    def body(req):
        try:
            payload = req.get_json()
        except ValueError:
            return _error("Request body must be valid JSON", 400)

        if not isinstance(payload, dict):
            return _error("JSON body must be an object", 400)
        if not payload.get("farm_id") or not payload.get("timestamp"):
            return _error("'farm_id' and 'timestamp' are required fields", 400)

        ts = payload.get("timestamp")
        if isinstance(ts, str):
            parsed, ok = _parse_dt(ts)
            if not ok or parsed is None:
                return _error("'timestamp' must be an ISO date/datetime string", 400)
            payload["timestamp"] = parsed

        collection = get_timeseries_collection()
        collection.insert_one(payload)
        payload.pop("_id", None)
        return _json({"inserted": payload}, status_code=201)

    return _handle(body, req)