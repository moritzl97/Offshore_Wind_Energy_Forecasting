import logging
import json
import os
import pandas as pd
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


# App & DB setup
load_dotenv("../.env")

app = func.FunctionApp()

MONGO_URI = os.environ["MONGO_URI"]
DB_NAME = os.environ["MONGO_DB"]
COLLECTION_NAME = os.environ["MONGO_COLLECTION"]

def get_collection():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME][COLLECTION_NAME]

# REST API
@app.route(route="windfarms", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_turbines(req: func.HttpRequest) -> func.HttpResponse:
    """Return a list of unique windfarm names."""
    # try:
    #     collection = get_collection()
    #     stations = collection.distinct("Station")
    #     return func.HttpResponse(
    #         json.dumps({"turbines": stations}, cls=DateTimeEncoder),
    #         mimetype="application/json",
    #         status_code=200,
    #     )
    # except PyMongoError as e:
    #     return func.HttpResponse(str(e), status_code=500)


@app.route(route="windfarms/{windfarm_name}/timeseries", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_timeseries(req: func.HttpRequest) -> func.HttpResponse:
    """
    Return timeseries (actual power, predicted power, wind speed) for a specific windfarm_name.
    ?start=&end=
    start and end parameter
    """
    # windfarm_name = req.route_params.get("windfarm_name")
    # start = req.params.get("start")
    # end = req.params.get("end")
    # limit = int(req.params.get("limit", 100))
    #
    # query: dict = {"Station": windfarm_name}
    #
    # if start or end:
    #     query["timestamp"] = {}
    #     if start:
    #         query["timestamp"]["$gte"] = start
    #     if end:
    #         query["timestamp"]["$lte"] = end
    #
    # try:
    #     collection = get_collection()
    #     cursor = collection.find(query, {"_id": 0}).limit(limit)
    #     records = list(cursor)
    #     return func.HttpResponse(
    #         json.dumps({"station": windfarm_name, "count": len(records), "readings": records}, cls=DateTimeEncoder),
    #         mimetype="application/json",
    #         status_code=200,
    #     )
    # except PyMongoError as e:
    #     return func.HttpResponse(str(e), status_code=500)

@app.route(route="windfarms/{windfarm_name}/metadata", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_metadata(req: func.HttpRequest) -> func.HttpResponse:
    """
    Return metadata for a specific windfarm_name.
    """
    # windfarm_name = req.route_params.get("windfarm_name")
    # start = req.params.get("start")
    # end = req.params.get("end")
    # limit = int(req.params.get("limit", 100))
    #
    # query: dict = {"Station": windfarm_name}
    #
    # if start or end:
    #     query["timestamp"] = {}
    #     if start:
    #         query["timestamp"]["$gte"] = start
    #     if end:
    #         query["timestamp"]["$lte"] = end
    #
    # try:
    #     collection = get_collection()
    #     cursor = collection.find(query, {"_id": 0}).limit(limit)
    #     records = list(cursor)
    #     return func.HttpResponse(
    #         json.dumps({"station": windfarm_name, "count": len(records), "readings": records}, cls=DateTimeEncoder),
    #         mimetype="application/json",
    #         status_code=200,
    #     )
    # except PyMongoError as e:
    #     return func.HttpResponse(str(e), status_code=500)

@app.route(route="timeseries", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def post_reading(req: func.HttpRequest) -> func.HttpResponse:
    """
    Insert a readings.
    Expected JSON body:
    {
      "farm_id": "Borssele_12",
      "records": [
        {"timestamp": "2026-06-15T00:00:00", "wind_speed_ms": 8.5},
        {"timestamp": "2026-06-15T01:00:00", "wind_speed_ms": 9.1},
        ...
      ]
    }
    """
    # try:
    #     body = req.get_json()
    # except ValueError:
    #     return func.HttpResponse("Invalid JSON body", status_code=400)
    #
    # if not body.get("Station") or not body.get("timestamp"):
    #     return func.HttpResponse("'Station' and 'timestamp' are required fields", status_code=400)
    #
    # try:
    #     collection = get_collection()
    #
    #     ts = body.get("timestamp")
    #     body["timestamp"] = datetime.fromisoformat(ts) if isinstance(ts, str) else ts
    #     collection.insert_one(body)
    #     body.pop("_id", None)
    #     # convert datetime back to string for JSON response
    #     body["timestamp"] = body["timestamp"].isoformat()
    #     return func.HttpResponse(
    #         json.dumps({"inserted": body}, cls=DateTimeEncoder),
    #         mimetype="application/json",
    #         status_code=201,
    #     )
    # except PyMongoError as e:
    #     return func.HttpResponse(str(e), status_code=500)