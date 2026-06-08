import pandas as pd
import json

def Offshore_wind_farm():
    path = "../datasets_raw/Analyzing_Europes_Biggest_Offshore_Wind_Farms/"
    raw_filenames = ["Borssele_(Phase_1,2).csv", "Borssele_(Phase_3,4).csv", "Gemini.csv", "Hollandse_Kust_Noord.csv",
                     "Hollandse_Kust_Zuid.csv"]
    wind_farm_names = ["Borssele_12", "Borssele_34", "Gemini", "Hollandse_Kust_Noord", "Hollandse_Kust_Zuid"]

    dfs = []

    for i, file in enumerate(raw_filenames):
        df = pd.read_csv(path + file)

        # drop unused columns
        df = df.drop(columns=["u100", "v100", "fsr", "Unnamed: 0"])
        df = df.drop(columns=[col for col in df.columns if col.startswith("Power_of_")])

        # Rename Scaled Windspeed
        df.columns = [col if not col.startswith("Scaled_Windspeed") else "Scaled_Windspeed" for col in df.columns]
        df = df.set_index("time")
        df.index = pd.to_datetime(df.index)
        df["Station"] = wind_farm_names[i]
        dfs.append(df)

    with open("../datasets/metadata_wind_farms.json") as f:
        wind_farms_metadata = json.load(f)["wind_farms"]

    capacities = {farm["id"]: farm["installed_capacity_mw"] for farm in wind_farms_metadata}

    for df, name in zip(dfs, wind_farm_names):
        capacity = capacities[name]
        df.loc[df["Power"] > capacity, "Power"] = capacity

        df.to_csv("../datasets/offshore_" + name + ".csv")

    return dfs