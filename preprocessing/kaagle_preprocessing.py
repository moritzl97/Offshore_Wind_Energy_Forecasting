import io
import pandas as pd


def preprocess_kaggle_content(raw_csv: str) -> pd.DataFrame:
    """
    Core function. Processes a single Kaggle SCADA CSV's raw content.
    Works for both local single-file calls and blob storage.
    """
    df_scada = pd.read_csv(io.StringIO(raw_csv))

    df_scada['Date/Time'] = pd.to_datetime(df_scada['Date/Time'], format='%d %m %Y %H:%M')

    df_scada['zero_power'] = df_scada['LV ActivePower (kW)'] == 0
    df_scada = df_scada[df_scada['LV ActivePower (kW)'] >= 0]

    df_scada = df_scada.set_index('Date/Time')

    df_scada_hourly = df_scada.resample('1h').agg({
        'LV ActivePower (kW)': 'mean',
        'Wind Speed (m/s)': 'mean',
        'Theoretical_Power_Curve (KWh)': 'mean',
        'Wind Direction (°)': 'mean',
        'zero_power': 'sum'
    })

    df_scada_hourly['LV ActivePower (MW)'] = df_scada_hourly['LV ActivePower (kW)'] / 1000
    df_scada_hourly['Theoretical_Power_Curve (MW)'] = df_scada_hourly['Theoretical_Power_Curve (KWh)'] / 1000

    return df_scada_hourly


def Kaagle(raw_data_path):
    """Local-file wrapper. Concatenates all CSVs in a folder, then processes."""
    files = sorted(raw_data_path.glob("*.csv"))
    dfs = []
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            raw_csv = f.read()
        dfs.append(pd.read_csv(io.StringIO(raw_csv)))

    df_combined = pd.concat(dfs, ignore_index=True)
    raw_combined_csv = df_combined.to_csv(index=False)
    return preprocess_kaggle_content(raw_combined_csv)