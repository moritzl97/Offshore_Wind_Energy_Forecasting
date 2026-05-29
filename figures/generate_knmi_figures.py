"""
Generate corrected KNMI figures for the report (Chapter 4 — Dataset KNMI section).
Station 209 = IJmond (near IJmuiden), the station in the repo's raw data.
Year 2019 to match the Figshare offshore dataset used elsewhere in the report.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

OUT = Path(__file__).parent          # save PNGs next to this script
RAW = Path(__file__).parent.parent / "datasets_raw" / "uurgeg_209_2011-2020.txt"

# ── Load & parse ────────────────────────────────────────────────────────────
df = pd.read_csv(RAW, skiprows=31, header=0, na_values=["     ", "   ", "  ", " ", ""])
df.columns = df.columns.str.strip()

df["HH_fixed"] = df["HH"].astype(int)
overflow = df["HH_fixed"] == 24
df.loc[overflow, "HH_fixed"] = 0
df["datetime_str"] = df["YYYYMMDD"].astype(str) + df["HH_fixed"].astype(str).str.zfill(2)
df["timestamp"] = pd.to_datetime(df["datetime_str"], format="%Y%m%d%H")
df.loc[overflow, "timestamp"] += pd.Timedelta(days=1)
df["timestamp"] += pd.Timedelta(hours=1)        # UTC → CET
df = df.set_index("timestamp").sort_index()

df = df.rename(columns={"DD": "wind_dir", "FH": "wind_speed_raw", "FF": "wind_speed_10min"})
df["wind_speed_ms"]  = df["wind_speed_raw"]  / 10.0
df["wind_speed_10min"] = df["wind_speed_10min"] / 10.0
df.loc[df["wind_dir"] > 360, "wind_dir"] = np.nan

# ── Filter to 2019 ──────────────────────────────────────────────────────────
y = df["2019-01-01":"2019-12-31"]

ws  = y["wind_speed_ms"].dropna()
wd  = y["wind_dir"].dropna()
wd  = wd[wd > 0]          # drop calm (0°) as it's a code, not a direction

# ── Statistics (print for the report table) ─────────────────────────────────
print("=== Station 209 (IJmond) — 2019 ===")
print(f"Rows: {len(y)}  |  Wind speed non-NaN: {len(ws)}  |  Wind dir non-NaN: {len(wd)}")
print(f"\nWind speed (m/s)")
print(f"  min    {ws.min():.2f}")
print(f"  max    {ws.max():.2f}")
print(f"  mean   {ws.mean():.2f}")
print(f"  median {ws.median():.2f}")
print(f"  std    {ws.std():.2f}")
print(f"\nWind direction (°)  [mean/median/std only — circular]")
print(f"  mean   {wd.mean():.1f}")
print(f"  median {wd.median():.1f}")
print(f"  std    {wd.std():.1f}")

# ── Fig 1: Time series ───────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(12, 3.5))
ax.plot(y.index, y["wind_speed_ms"], linewidth=0.5, color="#2c7bb6", alpha=0.85)
ax.set_ylabel("Wind speed (m/s)", fontsize=11)
ax.set_xlabel("Date (CET)", fontsize=11)
ax.set_title("Time series of hourly wind speed at KNMI station IJmond (209) in 2019", fontsize=12)
ax.set_ylim(0)
fig.tight_layout()
fig.savefig(OUT / "fig_knmi_timeseries_2019.png", dpi=150)
plt.close(fig)
print("\nSaved fig_knmi_timeseries_2019.png")

# ── Fig 2: Wind speed distribution ──────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 4))
ax.hist(ws, bins=range(0, 30), color="#2c7bb6", edgecolor="white", linewidth=0.5)
ax.axvline(ws.mean(), color="red", linewidth=1.5, linestyle="--", label=f"Mean {ws.mean():.1f} m/s")
ax.set_xlabel("Wind speed (m/s)", fontsize=11)
ax.set_ylabel("Frequency", fontsize=11)
ax.set_title("Wind speed distribution, IJmond (KNMI 209) 2019", fontsize=12)
ax.legend(fontsize=10)
fig.tight_layout()
fig.savefig(OUT / "fig_knmi_windspeed_dist_2019.png", dpi=150)
plt.close(fig)
print("Saved fig_knmi_windspeed_dist_2019.png")

# ── Fig 3: Wind direction distribution ──────────────────────────────────────
bins = np.arange(0, 380, 10)
fig, ax = plt.subplots(figsize=(8, 4))
ax.hist(wd, bins=bins, color="#2c7bb6", edgecolor="white", linewidth=0.4)
ax.set_xlabel("Wind direction (degrees)", fontsize=11)
ax.set_ylabel("Frequency", fontsize=11)
ax.set_title("Wind direction distribution, IJmond (KNMI 209) 2019", fontsize=12)
ax.set_xticks(range(0, 380, 45))
ax.set_xticklabels(["N\n0", "NE\n45", "E\n90", "SE\n135", "S\n180",
                     "SW\n225", "W\n270", "NW\n315", "N\n360"])
fig.tight_layout()
fig.savefig(OUT / "fig_knmi_winddir_dist_2019.png", dpi=150)
plt.close(fig)
print("Saved fig_knmi_winddir_dist_2019.png")

print("\nAll figures saved to:", OUT)
