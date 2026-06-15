import os
import pandas as pd
from pymongo import MongoClient

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER_PATH = os.path.join(BASE_DIR, "datasets")

MONGO_URI  = 'mongodb+srv://25092413_db_user:rZTgL0uPvIArdFen@cluster0.vffsegw.mongodb.net/?appName=Cluster0'
DB_NAME    = 'ProjectGroup3'
client     = MongoClient(MONGO_URI)
db         = client[DB_NAME]
collection = db['Group3']


SEARCHES = [
    {
        "search_term"     : "Power",           # column name to search for
        "location"        : "Borssele_12",     # farm name to store under in MongoDB
        "filename_filter" : "Borssele_12",     # only look in this CSV file
        "find_max"        : True,
        "find_min"        : True,
        "find_median"     : False,
    },
    {
        "search_term"     : "Windspeed",
        "location"        : "Gemini",
        "filename_filter" : "Gemini",
        "find_max"        : True,
        "find_min"        : False,
        "find_median"     : True,
    },
    {
        "search_term"     : "Power",
        "location"        : "Hollandse_Kust_Zuid",
        "filename_filter" : "Hollandse_Kust_Zuid",
        "find_max"        : True,
        "find_min"        : True,
        "find_median"     : True,
    },
]

UPDATES = [
    # {
    #     "location"        : "Borssele_12",     # which document to update
    #     "field_to_update" : "search_term",     # field to change
    #     "new_value"       : "WindPower",       # new value
    # },
]

def search_csv(search_term, find_max=False, find_min=False, find_median=False, filename_filter=None):
    print(FOLDER_PATH)
    results = []

    for filename in os.listdir(FOLDER_PATH):
        if not filename.endswith(".csv"):
            continue
        if filename_filter and filename_filter.lower() not in filename.lower():
            continue

        df = pd.read_csv(os.path.join(FOLDER_PATH, filename))

        for col in df.columns:
            if search_term.lower() in col.lower():
                numeric_col = pd.to_numeric(df[col], errors='coerce')

                if find_max or find_min or find_median:
                    row = {"file": filename, "column": col}
                    if find_max:
                        row["max"]    = numeric_col.max()
                    if find_min:
                        row["min"]    = numeric_col.min()
                    if find_median:
                        row["median"] = numeric_col.median()
                    results.append(row)
                else:
                    for _, r in df.iterrows():
                        results.append({
                            "file"  : filename,
                            "column": col,
                            "value" : r[col]
                        })

    if not results:
        print(f"  No matches found for '{search_term}'")
        return None

    result_df = pd.DataFrame(results)

    if not find_max and not find_min and not find_median:
        total     = len(result_df)
        result_df = result_df.head(20)
        print(f"  Showing {len(result_df)} of {total} results")

    print(result_df.to_string(index=False))
    return result_df

def insert_to_mongo(search_term, location, find_max, find_min, find_median, filename_filter):
    print(f"\n{'─' * 50}")
    print(f"  Searching  : '{search_term}'")
    print(f"  Location   : '{location}'")
    print(f"  File filter: '{filename_filter or 'all'}'")
    print(f"{'─' * 50}")

    result_df = search_csv(search_term, find_max, find_min, find_median, filename_filter)

    records  = result_df.to_dict(orient='records')
    document = {
        "location"   : location,
        "search_term": search_term,
        "data"       : records
    }

    collection.insert_one(document)
    print(f"\n  Inserted {len(records)} record(s) into MongoDB under '{location}'")


def update_in_mongo(location, field_to_update, new_value):
    print(f"\n{'─' * 50}")
    print(f"  Updating location '{location}': {field_to_update} → {new_value}")
    print(f"{'─' * 50}")

    result = collection.update_one(
        {"location": location},
        {"$set": {field_to_update: new_value}}
    )
    
    print(f"Updated '{field_to_update}' to '{new_value}' for '{location}'")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  Search Data → MongoDB")
    print("=" * 50)

    #for s in SEARCHES:
        #insert_to_mongo(
        #    search_term    = s["search_term"],
        #    location       = s["location"],
        #    find_max       = s.get("find_max", False),
        #    find_min       = s.get("find_min", False),
        #    find_median    = s.get("find_median", False),
        #    filename_filter= s.get("filename_filter", None),
        #)
        
    for u in UPDATES:
        update_in_mongo(
            location       = u["location"],
            field_to_update= u["field_to_update"],
            new_value      = u["new_value"],
        )

    print("\n" + "=" * 50)
    print("  Done")
    print("=" * 50)
    client.close()