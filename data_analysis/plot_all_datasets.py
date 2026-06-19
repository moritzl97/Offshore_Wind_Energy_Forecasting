"""
Plot for each dataset.

Generates a consistent two-panel overview (time series + value distribution) for
every dataset used in the project, so each source can be inspected on its own
before the cross-dataset power-curve comparison. ENTSOE has its own dedicated
script (plot_entsoe_overview.py); this covers the remaining datasets:

  - Kaggle SCADA single turbine (T1.csv, 2018)
  - Hollandse Kust Zuid offshore farm (modelled, sampled year 2019)
  - KNMI station 209 weather (2019)

Outputs (figures/):
  fig_kaggle_timeseries.png        fig_kaggle_distribution.png
  fig_hkz_timeseries.png           fig_hkz_distribution.png
  fig_knmi209_timeseries.png       fig_knmi209_distribution.png

Author: Noah Mignola
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)


def save_timeseries(t, y, ylabel, title, fname, color):
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(t, y, linewidth=0.5, color=color)
    ax.set_xlabel("Date")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / fname, dpi=150)
    plt.close(fig)


def save_distribution(y, xlabel, title, fname, color):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(y.dropna(), bins=50, color=color, edgecolor="black", alpha=0.8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Frequency (records)")
    ax.set_title(title)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / fname, dpi=150)
    plt.close(fig)


def plot_kaggle():
    df = pd.read_csv(ROOT / "datasets_raw" / "kaggle_dataset" / "T1.csv")
    df["Date/Time"] = pd.to_datetime(df["Date/Time"], format="%d %m %Y %H:%M")
    power = df["LV ActivePower (kW)"]
    save_timeseries(df["Date/Time"], power, "Active power (kW)",
                    "Kaggle SCADA single turbine - power output (2018)",
                    "fig_kaggle_timeseries.png", "tab:orange")
    save_distribution(power, "Active power (kW)",
                      "Kaggle SCADA single turbine - power distribution (2018)",
                      "fig_kaggle_distribution.png", "tab:orange")


def plot_hkz():
    df = pd.read_csv(ROOT / "datasets_raw" / "offshore_dataset" / "Hollandse_Kust_Zuid.csv")
    df["time"] = pd.to_datetime(df["time"])
    # 40-year modelled record (1980-2019); show 2019 to match the project reference year
    df_2019 = df[df["time"].dt.year == 2019]
    save_timeseries(df_2019["time"], df_2019["Power"], "Farm power (MW)",
                    "Hollandse Kust Zuid (modelled) - farm power output (2019)",
                    "fig_hkz_timeseries.png", "tab:green")
    save_distribution(df["Power"], "Farm power (MW)",
                      "Hollandse Kust Zuid (modelled) - power distribution (1980-2019)",
                      "fig_hkz_distribution.png", "tab:green")


def plot_knmi209():
    df = pd.read_csv(ROOT / "datasets" / "knmi_209_2019.csv", parse_dates=["timestamp"])
    save_timeseries(df["timestamp"], df["wind_speed_ms"], "Wind speed (m/s)",
                    "KNMI station 209 (IJmond) - wind speed (2019)",
                    "fig_knmi209_timeseries.png", "tab:blue")
    save_distribution(df["wind_speed_ms"], "Wind speed (m/s)",
                      "KNMI station 209 (IJmond) - wind speed distribution (2019)",
                      "fig_knmi209_distribution.png", "tab:blue")


def main():
    plot_kaggle()
    plot_hkz()
    plot_knmi209()
    print(f"Saved per-dataset overview figures to {FIG_DIR}")


if __name__ == "__main__":
    main()
