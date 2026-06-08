import pandas as pd
from pathlib import Path

DATA_DIR = Path("../datasets")

wind = pd.read_csv(DATA_DIR / "wind_turbine_train_clean.csv")
entso = pd.read_csv(DATA_DIR / "ENTSO_installed_capacity_offshore.csv")

annual_power = wind.groupby("year", as_index=False).agg(
    kaggle_avg_power=("Power", "mean"),
    kaggle_avg_wind_speed_100m=("WS_100m", "mean"),
    kaggle_avg_temperature_2m=("Temp_2m", "mean"),
    kaggle_rows=("Power", "size"),
)

merged = pd.merge(annual_power, entso, on="year", how="left")
merged.to_csv(DATA_DIR / "merged_kaggle_entso_yearly.csv", index=False)

print("Saved merged_kaggle_entso_yearly.csv")