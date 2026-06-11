"""
Plot for each dataset: ENTSOE NL offshore wind generation.

Produces a time series plot and a distribution plot for the compiled ENTSOE
dataset, in the same style as the existing fig_knmi_* figures.

Input:  datasets/entsoe_nl_offshore_wind.csv
Output: figures/fig_entsoe_timeseries_2019.png
        figures/fig_entsoe_distribution_2019.png
        figures/fig_entsoe_timeseries_full.png

Author: Noah Mignola
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)


def load_entsoe():
    df = pd.read_csv(ROOT / "datasets" / "entsoe_nl_offshore_wind.csv",
                      parse_dates=["Datetime"], index_col="Datetime")
    return df


def plot_timeseries_2019(df: pd.DataFrame):
    df_2019 = df.loc["2019-01-01":"2019-12-31"]

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(df_2019.index, df_2019["Generation_MW"], linewidth=0.5, color="tab:blue")
    ax.set_xlabel("Date")
    ax.set_ylabel("Generation (MW)")
    ax.set_title("ENTSOE NL offshore wind generation - 2019")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_entsoe_timeseries_2019.png", dpi=150)
    plt.close(fig)


def plot_distribution_2019(df: pd.DataFrame):
    df_2019 = df.loc["2019-01-01":"2019-12-31"]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(df_2019["Generation_MW"], bins=50, color="tab:blue", edgecolor="black", alpha=0.8)
    ax.set_xlabel("Generation (MW)")
    ax.set_ylabel("Frequency (hours)")
    ax.set_title("ENTSOE NL offshore wind generation distribution - 2019")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_entsoe_distribution_2019.png", dpi=150)
    plt.close(fig)


def plot_timeseries_full(df: pd.DataFrame):
    annual = df["Generation_MW"].resample("D").mean()

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(annual.index, annual.values, linewidth=0.7, color="tab:blue")
    ax.set_xlabel("Date")
    ax.set_ylabel("Daily mean generation (MW)")
    ax.set_title("ENTSOE NL offshore wind generation - full period (daily mean)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_entsoe_timeseries_full.png", dpi=150)
    plt.close(fig)


def main():
    df = load_entsoe()
    plot_timeseries_2019(df)
    plot_distribution_2019(df)
    plot_timeseries_full(df)
    print(f"Saved ENTSOE overview figures to {FIG_DIR}")


if __name__ == "__main__":
    main()
