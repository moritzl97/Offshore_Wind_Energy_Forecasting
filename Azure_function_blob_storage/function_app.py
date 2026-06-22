import logging
import io
import json
import os

import azure.functions as func
from pymongo import MongoClient
import pandas as pd
from azure.storage.blob import BlobServiceClient

from knmi_preprocessing import preprocess_knmi_content
from offshore_preprocessing import preprocess_wind_farm_content
from kaagle_preprocessing import preprocess_kaggle_content
from entsoe_preprocessing import preprocess_entsoe_content

# ---------- App & DB setup ----------

app = func.FunctionApp()

MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB  = os.environ["MONGO_DB"]
METADATA_COL = os.environ["MONGO_COLLECTION_METADATA"]
AZURE_STORAGE_CONNECTION_STRING = os.environ["AzureWebJobsStorage"]

PROCESSED_CONTAINER = "processed"

# ---------- Helper functions ----------
def get_farm_capacity(farm_name: str):
    """
    Fetch just the installed_capacity_mw for a given farm.
    Returns None if the farm or the field doesn't exist.
    """
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    doc = db[METADATA_COL].find_one(
        {"_id": farm_name},
        {"installed_capacity_mw": 1, "_id": 0}
    )
    return doc.get("installed_capacity_mw") if doc else None


def get_known_farm_names() -> list:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    doc = db[METADATA_COL].find_one({"wind_farms": {"$exists": True}})
    if not doc:
        return []
    return list(doc.get("wind_farms", {}).keys())


def merge_with_existing(new_df: pd.DataFrame, processed_filename: str, index_col: str = None) -> pd.DataFrame:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(
        container=PROCESSED_CONTAINER,
        blob=processed_filename
    )

    try:
        existing_bytes = blob_client.download_blob().readall()
        existing_df = pd.read_csv(io.BytesIO(existing_bytes), index_col=index_col)
        if index_col:
            existing_df.index = pd.to_datetime(existing_df.index, errors="coerce")
        logging.info(f"Found existing processed file '{processed_filename}' with {len(existing_df)} rows")
    except Exception:
        logging.info(f"No existing processed file '{processed_filename}' found, starting fresh")
        existing_df = pd.DataFrame()

    combined = pd.concat([existing_df, new_df])

    if index_col:
        combined.index = pd.to_datetime(combined.index, errors="coerce")

    combined = combined[~combined.index.duplicated(keep="last")]
    combined = combined.sort_index()

    return combined

############ Blob ingest trigger ########
# ---------- KNMI blob trigger ----------
@app.blob_trigger(
    arg_name="blob",
    path="raw-knmi/{name}.txt",
    connection="AzureWebJobsStorage"
)
def knmi_blob_trigger(blob: func.InputStream) -> None:
    logging.info(f"KNMI blob trigger fired for: {blob.name}")
    try:
        filename = blob.name.split("/")[-1]

        # station name is everything before the first underscore, with spaces replaced
        station_name = filename.split("_")[0].replace(" ", "_")

        raw_text = blob.read().decode("utf-8", errors="replace")
        new_df = preprocess_knmi_content(raw_text, filename)

        processed_filename = f"knmi_{station_name}.csv"
        merged_df = merge_with_existing(new_df, processed_filename, index_col="timestamp")

        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        out_client = blob_service_client.get_blob_client(
            container=PROCESSED_CONTAINER,
            blob=processed_filename
        )
        out_client.upload_blob(merged_df.to_csv().encode("utf-8"), overwrite=True)

        logging.info(f"KNMI merge complete for station '{station_name}', total {len(merged_df)} rows")
    except Exception as e:
        logging.error(f"KNMI preprocessing failed for {blob.name}: {e}")


# ---------- ENTSOE blob trigger ----------
@app.blob_trigger(
    arg_name="blob",
    path="raw-entsoe/{name}.csv",
    connection="AzureWebJobsStorage"
)
def entsoe_blob_trigger(blob: func.InputStream) -> None:
    logging.info(f"ENTSOE blob trigger fired for: {blob.name}")
    try:
        raw_text = blob.read().decode("utf-8", errors="replace")
        new_df = preprocess_entsoe_content(raw_text)

        processed_filename = "entsoe.csv"
        merged_df = merge_with_existing(new_df, processed_filename, index_col="Datetime")

        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        out_client = blob_service_client.get_blob_client(
            container=PROCESSED_CONTAINER,
            blob=processed_filename
        )
        out_client.upload_blob(merged_df.to_csv().encode("utf-8"), overwrite=True)

        logging.info(f"ENTSOE merge complete, total {len(merged_df)} rows")
    except Exception as e:
        logging.error(f"ENTSOE preprocessing failed for {blob.name}: {e}")


# ---------- Kaggle blob trigger ----------
@app.blob_trigger(
    arg_name="blob",
    path="raw-kaggle/{name}.csv",
    connection="AzureWebJobsStorage"
)
def kaggle_blob_trigger(blob: func.InputStream) -> None:
    logging.info(f"Kaggle blob trigger fired for: {blob.name}")
    try:
        raw_text = blob.read().decode("utf-8", errors="replace")
        new_df = preprocess_kaggle_content(raw_text)

        processed_filename = "kaggle.csv"
        merged_df = merge_with_existing(new_df, processed_filename, index_col="Date/Time")

        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        out_client = blob_service_client.get_blob_client(
            container=PROCESSED_CONTAINER,
            blob=processed_filename
        )
        out_client.upload_blob(merged_df.to_csv().encode("utf-8"), overwrite=True)

        logging.info(f"Kaggle merge complete, total {len(merged_df)} rows")
    except Exception as e:
        logging.error(f"Kaggle preprocessing failed for {blob.name}: {e}")


# ---------- Offshore blob trigger ----------
@app.blob_trigger(
    arg_name="blob",
    path="raw-offshore/{name}.csv",
    connection="AzureWebJobsStorage")
def offshore_blob_trigger(blob: func.InputStream) -> None:
    logging.info(f"Offshore blob trigger fired for: {blob.name}")
    try:
        filename = blob.name.split("/")[-1]
        farm_name = filename.split(".")[0]

        if not farm_name:
            logging.warning(f"Could not match filename '{filename}' to a known farm")
            farm_name = filename.replace(".csv", "")

        capacity_mw = get_farm_capacity(farm_name)
        if capacity_mw is None:
            logging.warning(f"No capacity found for '{farm_name}', skipping cap")

        raw_text = blob.read().decode("utf-8", errors="replace")
        new_df = preprocess_wind_farm_content(raw_text, farm_name, capacity_mw)

        processed_filename = f"offshore_{farm_name}.csv"
        merged_df = merge_with_existing(new_df, processed_filename, index_col="time")

        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        out_client = blob_service_client.get_blob_client(
            container=PROCESSED_CONTAINER,
            blob=processed_filename
        )
        out_client.upload_blob(merged_df.to_csv().encode("utf-8"), overwrite=True)

        logging.info(f"Offshore merge complete for farm '{farm_name}', total {len(merged_df)} rows")
    except Exception as e:
        logging.error(f"Offshore preprocessing failed for {blob.name}: {e}")