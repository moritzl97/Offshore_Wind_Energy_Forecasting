"""
Preprocessing script — Figshare offshore and WINS50 datasets.
Run from repo root:  python preprocessing/run_preprocessing.py
Outputs -> datasets/
"""
import zipfile, re
from pathlib import Path
import numpy as np
import pandas as pd

RAW_OFFSHORE = Path("datasets_raw/Analyzing_Europes_Biggest_Offshore_Wind_Farms")
RAW_WINS50   = Path("datasets_raw/WINS50")
OUT          = Path("datasets")
OUT.mkdir(exist_ok=True)

FARMS = {
    "Borssele_12":          {"file": "Borssele_(Phase_1,2).csv", "cap_mw": 736},
    "Borssele_34":          {"file": "Borssele_(Phase_3,4).csv", "cap_mw": 716},
    "Gemini":               {"file": "Gemini.csv",               "cap_mw": 600},
    "Hollandse_Kust_Noord": {"file": "Hollandse_Kust_Noord.csv", "cap_mw": 760},
    "Hollandse_Kust_Zuid":  {"file": "Hollandse_Kust_Zuid.csv",  "cap_mw": 1540},
}

# ── PART 1: Figshare Offshore ────────────────────────────────────────────────
print("=== PART 1: Figshare Offshore Wind Farms ===")

for farm_name, meta in FARMS.items():
    df = pd.read_csv(RAW_OFFSHORE / meta["file"])
    cap = meta["cap_mw"]

    # Drop unused raw columns
    drop = ["Unnamed: 0", "u100", "v100", "fsr"] + \
           [c for c in df.columns if c.startswith("Power_of_")]
    df = df.drop(columns=[c for c in drop if c in df.columns])

    # Normalise scaled windspeed column name; record hub height
    scaled = [c for c in df.columns if c.startswith("Scaled_Windspeed")]
    if scaled:
        hub = re.search(r"\((.*?)\)", scaled[0])
        df["hub_height"] = hub.group(1) if hub else "unknown"
        df = df.rename(columns={scaled[0]: "Scaled_Windspeed"})

    # Parse timestamps, set UTC-aware index
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()
    df["farm"]   = farm_name
    df["cap_mw"] = cap

    # Quality flags (flag, don't drop)
    df["flag_cutout"]         = (df["Scaled_Windspeed"] >= 25) & (df["Power"] < cap * 0.01)
    df["flag_over_capacity"]  = df["Power"] > cap * 1.05
    df["flag_turnoff_mismatch"] = (
        ((df["Turn_off"] == 0) & (df["Power"] > 0)) |
        ((df["Turn_off"] == 1) & (df["Power"] == 0))
    )

    # QC summary
    full_idx = pd.date_range(df.index.min(), df.index.max(), freq="h", tz="UTC")
    print(f"\n{farm_name} ({cap} MW)  rows={len(df)}")
    print(f"  Missing hours: {len(full_idx.difference(df.index))}  Duplicates: {df.index.duplicated().sum()}")
    print(f"  Neg power: {(df['Power']<0).sum()}  Over cap: {df['flag_over_capacity'].sum()}")
    print(f"  Cut-out events: {df['flag_cutout'].sum()}")
    print(f"  Turn_off mismatch: {df['flag_turnoff_mismatch'].sum()}")

    df.to_csv(OUT / f"offshore_{farm_name}.csv")
    print(f"  Saved offshore_{farm_name}.csv")

print("\nPart 1 complete.")


# ── PART 2: WINS50 ──────────────────────────────────────────────────────────
print("\n=== PART 2: WINS50 HARMONIE ===")

try:
    import geopandas as gpd

    POWER_ZIP = RAW_WINS50 / "wins50_harmonie_windfarm_powerproduction.zip"
    LOOKUP    = RAW_WINS50 / "wins50_singlepoint_lookuptable.csv"
    SHAPE     = RAW_WINS50 / "wins50_windfarm_scenarios.shp"

    def norm(s):
        return re.sub(r'[^a-z0-9]', '', str(s).lower())

    # Farm metadata from shapefile
    g = gpd.read_file(SHAPE)
    g["key"] = g["name"].map(norm)

    def summarise(df_g):
        op  = df_g[df_g["Scenario"].isin([2019, 2020, 2021])]
        c   = df_g.geometry.union_all().centroid
        big = df_g.sort_values("MW").iloc[-1]
        return pd.Series({
            "farm": df_g["name"].iloc[0], "country": df_g["country"].iloc[0],
            "cap_op_MW":   op["MW"].max() if len(op) else np.nan,
            "cap_2050_MW": df_g["MW"].max(),
            "turb_type": big["Turb_type"], "hub_z_m": big["z"],
            "lat": round(c.y, 4), "lon": round(c.x, 4),
        })

    meta = g.groupby("key").apply(summarise, include_groups=False).reset_index()

    # Nearest HARMONIE grid cell per farm
    lut = pd.read_csv(LOOKUP)
    LAT, LON = lut.lat.values, lut.lon.values
    IX,  IY  = lut.ix.values, lut.iy.values

    def nearest(lat, lon):
        d = (LAT - lat)**2 + ((LON - lon) * np.cos(np.radians(lat)))**2
        j = d.argmin()
        return IX[j], IY[j], round(LAT[j], 4), round(LON[j], 4)

    meta[["grid_ix","grid_iy","grid_lat","grid_lon"]] = [
        nearest(r.lat, r.lon) for r in meta.itertuples()
    ]

    # Filter to farms with a power timeseries
    zf = zipfile.ZipFile(POWER_ZIP)
    power_files = {norm(n.split("powerproduction_")[1][:-4]): n
                   for n in zf.namelist() if n.endswith(".csv")}
    meta = meta[meta.key.isin(power_files)].sort_values(["country","farm"]).reset_index(drop=True)
    meta.to_csv(OUT / "wins50_farm_metadata.csv", index=False)
    print(f"Farm metadata: {len(meta)} farms  ({(meta.country=='NL').sum()} NL)")

    # Load NL farms only
    nl = meta[meta.country == "NL"].copy()
    frames = []
    for k in nl.key:
        d = pd.read_csv(zf.open(power_files[k]))
        d.columns = ["dt", "P_op_MW", "P_2050_MW"]
        d["key"] = k
        frames.append(d)

    power = pd.concat(frames, ignore_index=True)
    power["dt"] = pd.to_datetime(power["dt"], format="%Y%m%d%H")

    # QC
    full_year = pd.date_range("2020-01-01", "2020-12-31 23:00", freq="h")
    print(f"Rows: {len(power)}  NL farms: {power.key.nunique()}")
    print(f"Missing timestamps (max per farm): {power.groupby('key')['dt'].apply(lambda s: (~full_year.isin(s)).sum()).max()}")
    print(f"Negative P_2050_MW: {(power['P_2050_MW']<0).sum()}")
    print(f"W20 NaN share: {power['P_op_MW'].isna().mean():.0%} (expected -- farms not built by 2020)")

    # NL national aggregate
    agg = power.groupby("dt")[["P_op_MW","P_2050_MW"]].sum(min_count=1).reset_index()
    agg.to_csv(OUT / "wins50_nl_offshore_aggregate.csv", index=False)
    print(f"NL aggregate saved  ({agg['P_2050_MW'].mean()/1000:.1f} GW mean, 2050)")

    print("\nPart 2 complete.")

except ImportError:
    print("geopandas not installed. Run: pip install geopandas")
except Exception as e:
    import traceback; traceback.print_exc()
