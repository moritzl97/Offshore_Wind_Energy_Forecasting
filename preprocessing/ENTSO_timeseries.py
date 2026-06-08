import pandas as pd
import os


def ENTSO_timeseries():
    path_raw = "../datasets_raw/ENTSO_timeseries/"

    raw_files = [f for f in os.listdir(path_raw)]

    # End product with a time series and total offshore power
    df_full_timeseries = pd.DataFrame()

    for file in raw_files:
        df = pd.read_csv(path_raw + file, low_memory=False)

        # Filter for Offshore Wind only
        df = df[df["Production Type"] == "Wind Offshore"]

        # Extract just the start time from the range string
        df["Datetime"] = pd.to_datetime(
            df["MTU (CET/CEST)"]
            .str.split(" - ").str[0]
            .str.replace(r"\(.*?\)", "", regex=True)
            .str.strip(),
            dayfirst=True
        )

        # Keep only the needed columns
        df =df[["Datetime", "Generation (MW)"]]

        # Rename for better consistency
        df.rename(columns={"Generation (MW)": "Generation_MW"}, inplace=True)

        # Convert to numeric data
        df["Generation_MW"] = pd.to_numeric(df["Generation_MW"], errors="coerce")

        # Check if file is empty (None or 0 values)
        if (df["Generation_MW"].fillna(0) == 0).all():
            print(f"Skipping {file}")
            continue

        # Set datetime as index
        df = df.set_index("Datetime")

        # Rename to hourly timestamps
        df = df.resample("h").mean()

        # Append to full time series df
        df_full_timeseries = pd.concat([df_full_timeseries, df])

        # For incomplete year (days in the future), search for last valid entry and drop that day and consecutive days
    last_valid = df_full_timeseries["Generation_MW"].last_valid_index()
    if last_valid:
        last_valid_day = last_valid.date()
        df_full_timeseries = df_full_timeseries[df_full_timeseries.index.date < last_valid_day]

    # Forward fill daylight saving times
    df_full_timeseries = df_full_timeseries.ffill(limit=1)

    return df_full_timeseries
