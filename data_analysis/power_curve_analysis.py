"""
Power curve comparison across datasets.

Builds the empirical power curve (wind speed vs. power output) for the
ENTSOE NL offshore wind generation time series (paired with KNMI hub-height
wind speed) and compares it against the previously analysed Sprint-1 power
curves: the single-turbine Kaggle SCADA dataset and the Hollandse Kust Zuid
offshore farm aggregate.

Inputs:
  datasets/entsoe_nl_offshore_wind.csv
  datasets/knmi_209_2019.csv
  datasets_raw/kaggle_dataset/T1.csv
  datasets_raw/offshore_dataset/Hollandse_Kust_Zuid.csv

Outputs:
  figures/fig_power_curve_entsoe.png
  figures/fig_power_curve_comparison.png

Author: Noah Mignola
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)

# NL offshore installed capacity grew ~5x between 2015 and 2026 as new farms came
# online (Borssele, Hollandse Kust Noord/Zuid, ...). To get a meaningful power curve
# (a fixed transfer function for a fixed fleet), the analysis is restricted to 2019 -
# the reference year used throughout the report for both KNMI station 209 and the
# ENTSOE NL offshore data (max ~885 MW, stable capacity). Only 2019 KNMI data is
# needed, so we read the slim datasets/knmi_209_2019.csv rather than the full record.
ENTSOE_PERIOD = ("2019-01-01", "2019-12-31 23:59:59")
ENTSOE_CAPACITY_MW = 885.5  # max NL offshore generation observed in 2019


def load_entsoe_knmi():
    entsoe = pd.read_csv(ROOT / "datasets" / "entsoe_nl_offshore_wind.csv",
                          parse_dates=["Datetime"], index_col="Datetime")
    entsoe = entsoe.loc[ENTSOE_PERIOD[0]:ENTSOE_PERIOD[1]]

    knmi = pd.read_csv(ROOT / "datasets" / "knmi_209_2019.csv",
                        parse_dates=["timestamp"], index_col="timestamp")
    knmi = knmi[["wind_speed_hub_ms"]]

    merged = entsoe.join(knmi, how="inner").dropna()
    merged = merged.rename(columns={"Generation_MW": "Power",
                                     "wind_speed_hub_ms": "WindSpeed"})
    return merged


def load_kaggle():
    df = pd.read_csv(ROOT / "datasets_raw" / "kaggle_dataset" / "T1.csv")
    df = df.rename(columns={"Wind Speed (m/s)": "WindSpeed",
                             "LV ActivePower (kW)": "Power"})
    return df[["WindSpeed", "Power"]].dropna()


def load_hollandse_kust_zuid():
    df = pd.read_csv(ROOT / "datasets_raw" / "offshore_dataset" / "Hollandse_Kust_Zuid.csv")
    df = df.rename(columns={"Scaled_Windspeed_(at_125.5m)": "WindSpeed",
                             "Power": "Power"})
    return df[["WindSpeed", "Power"]].dropna()


def plot_entsoe_power_curve(merged: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(merged["WindSpeed"], merged["Power"], s=4, alpha=0.15, color="tab:blue")
    ax.set_xlabel("KNMI hub-height wind speed (m/s)")
    ax.set_ylabel("ENTSOE NL offshore wind generation (MW)")
    ax.set_title("Power curve - ENTSOE NL offshore wind vs KNMI wind speed (2019)")
    ax.set_xlim(0, merged["WindSpeed"].quantile(0.999))
    ax.set_ylim(0, merged["Power"].max() * 1.05)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_power_curve_entsoe.png", dpi=150)
    plt.close(fig)


def plot_comparison(merged: pd.DataFrame, kaggle: pd.DataFrame, hkz: pd.DataFrame):
    datasets = {
        "Kaggle SCADA\n(single turbine, ~3,600 kW)": (kaggle, "tab:orange", 3600),
        "Hollandse Kust Zuid\n(farm aggregate, 1,540 MW)": (hkz, "tab:green", 1540),
        "ENTSOE NL offshore\n(national, ~885 MW, 2019)": (merged, "tab:blue", ENTSOE_CAPACITY_MW),
    }

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
    for ax, (label, (df, color, capacity)) in zip(axes, datasets.items()):
        norm_power = df["Power"] / capacity
        ax.scatter(df["WindSpeed"], norm_power, s=3, alpha=0.1, color=color)
        ax.set_title(label, fontsize=10)
        ax.set_xlabel("Wind speed (m/s)")
        ax.set_xlim(0, 30)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Normalised power output (fraction of rated capacity)")
    axes[0].set_ylim(0, 1.1)

    fig.suptitle("Power curve comparison: aggregation broadens the cut-in/rated transition", y=1.02)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_power_curve_comparison.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def summarize(name: str, df: pd.DataFrame, capacity: float):
    cf = (df["Power"] / capacity).mean()
    print(f"{name}: n={len(df):,}, capacity factor={cf:.3f}, "
          f"max power={df['Power'].max():.1f}, "
          f"wind speed range={df['WindSpeed'].min():.1f}-{df['WindSpeed'].max():.1f} m/s")


def main():
    merged = load_entsoe_knmi()
    kaggle = load_kaggle()
    hkz = load_hollandse_kust_zuid()

    print(f"ENTSOE-KNMI overlap: {merged.index.min()} -> {merged.index.max()} "
          f"({len(merged):,} hourly rows)")
    summarize("Kaggle SCADA", kaggle, 3600)
    summarize("Hollandse Kust Zuid", hkz, 1540)
    summarize("ENTSOE NL offshore", merged, ENTSOE_CAPACITY_MW)

    plot_entsoe_power_curve(merged)
    plot_comparison(merged, kaggle, hkz)
    print(f"\nFigures saved to {FIG_DIR}")


if __name__ == "__main__":
    main()
