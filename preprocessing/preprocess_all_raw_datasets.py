import numpy as np
try:
    from .entsoe_preprocessing import ENTSO_timeseries
    from .kaagle_preprocessing import Kaagle
    from .knmi_preprocessing import preprocess_knmi_file
    from .offshore_preprocessing import preprocess_wind_farm
except ImportError:
    from entsoe_preprocessing import ENTSO_timeseries
    from kaagle_preprocessing import Kaagle
    from knmi_preprocessing import preprocess_knmi_file
    from offshore_preprocessing import preprocess_wind_farm
from pathlib import Path
import json
import re
import pandas as pd


def preprocess_all(root_path: Path = None):
    if root_path is None:
        root_path = Path(__file__).resolve().parent.parent
    input_path = root_path / "datasets_raw"
    output_path = root_path / "datasets"

    output_path.mkdir(parents=True, exist_ok=True)

    print("-" * 50)

    print("Running ENTSO preprocessing")
    raw_dataset_path = input_path / "entsoe_dataset"
    if any(raw_dataset_path.iterdir()):
        try:
            preprocessed_entsoe_df = ENTSO_timeseries(raw_dataset_path)
            preprocessed_entsoe_df.to_csv(output_path / "entsoe.csv")
            print("preprocessed ENTSOE dataset saved.")

        except Exception as e:
            print(f"ENTSO preprocessing failed {e}")
    else:
        print(f"{raw_dataset_path} is empty.")
    print("-" * 50)

    print("Running Kaagle preprocessing")
    raw_dataset_path = input_path / "kaggle_dataset"
    if any(raw_dataset_path.iterdir()):
        try:
            preprocessed_kaggle_df = Kaagle(raw_dataset_path)
            preprocessed_kaggle_df.to_csv(output_path / "kaggle.csv")
            print("preprocessed Kaggle dataset saved.")

        except Exception as e:
            print(f"Kaggle preprocessing failed {e}")
    else:
        print(f"{raw_dataset_path} is empty.")
    print("-" * 50)

    print("Running KNMI preprocessing")
    raw_dataset_path = input_path / "knmi_dataset"
    start_year = 2015

    if any(raw_dataset_path.iterdir()):
        # try:
            filenames = [f.name for f in sorted(raw_dataset_path.glob("*.txt"))]

            station_dfs = {}
            for file in filenames:
                filepath = raw_dataset_path / file
                df = preprocess_knmi_file(filepath, start_year=start_year)
                station = df["Station"].iloc[0]
                safe_name = re.sub(r"[^A-Za-z0-9_]+", "_", station).strip("_")

                if safe_name in station_dfs:
                    station_dfs[safe_name].append(df)
                else:
                    station_dfs[safe_name] = [df]

            for safe_name, dfs in station_dfs.items():
                combined = pd.concat(dfs, ignore_index=True).sort_values("timestamp")
                combined.to_csv(output_path / f"knmi_{safe_name}.csv", index=False)

            print("Preprocessed KNMI dataset saved.")

        # except Exception as e:
        #     print(f"KNMI preprocessing failed: {e}")
    else:
        print(f"{raw_dataset_path} is empty.")
    print("-" * 50)

    print("Running Offshore preprocessing")
    raw_dataset_path = input_path / "offshore_dataset"
    if any(raw_dataset_path.iterdir()):
        try:
            files = {
                "Borssele_12": "Borssele_(Phase_1,2).csv",
                "Borssele_34": "Borssele_(Phase_3,4).csv",
                "Gemini": "Gemini.csv",
                "Hollandse_Kust_Noord": "Hollandse_Kust_Noord.csv",
                "Hollandse_Kust_Zuid": "Hollandse_Kust_Zuid.csv",
            }

            with open(root_path / "metadata_wind_farms.json") as f:
                wind_farms_metadata = json.load(f)["wind_farms"]

            capacities = {farm["id"]: farm["installed_capacity_mw"] for farm in wind_farms_metadata}
            for farm_name, filename in files.items():
                df = preprocess_wind_farm(
                    path=raw_dataset_path / filename,
                    farm_name=farm_name,
                    capacity_mw=capacities[farm_name],
                )
                df.to_csv(output_path / f"offshore_{farm_name}.csv")
            print("preprocessed Offshore dataset saved.")

        except Exception as e:
            print(f"Offshore preprocessing failed {e}")
    else:
        print(f"{raw_dataset_path} is empty.")
    print("-" * 50)

    print("Done")

if __name__ == "__main__":
    preprocess_all()