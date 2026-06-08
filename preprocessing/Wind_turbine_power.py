import pandas as pd
import numpy as np
from pathlib import Path

def clean_wind_dataset(df):
    df = df.copy()

    if 'Unnamed: 0' in df.columns:
        df = df.drop(columns=['Unnamed: 0'])

    df.columns = [c.strip() for c in df.columns]
    df['Time'] = pd.to_datetime(df['Time'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Time'])
    df = df.drop_duplicates()
    df = df.sort_values(['Location', 'Time']).reset_index(drop=True)

    for col in df.columns:
        if col != 'Time':
            df[col] = pd.to_numeric(df[col], errors='coerce')

    numeric_cols = [c for c in df.columns if c != 'Time']
    df[numeric_cols] = df.groupby('Location')[numeric_cols].transform(
        lambda s: s.interpolate(limit_direction='both')
    )

    df['year'] = df['Time'].dt.year
    df['month'] = df['Time'].dt.month
    df['day'] = df['Time'].dt.day
    df['hour'] = df['Time'].dt.hour
    df['date'] = df['Time'].dt.date.astype(str)

    df['wind_speed_difference_100m_10m'] = df['WS_100m'] - df['WS_10m']
    df['wind_speed_100m_squared'] = df['WS_100m'] ** 2
    df['wind_speed_100m_cubed'] = df['WS_100m'] ** 3

    df['wind_direction_100m_sin'] = np.sin(np.radians(df['WD_100m']))
    df['wind_direction_100m_cos'] = np.cos(np.radians(df['WD_100m']))
    df['wind_direction_10m_sin'] = np.sin(np.radians(df['WD_10m']))
    df['wind_direction_10m_cos'] = np.cos(np.radians(df['WD_10m']))

    return df

def Wind_turbine_power():
    RAW_DIR = Path('../datasets_raw/wind_turbine_power')
    OUT_DIR = Path('../datasets')
    OUT_DIR.mkdir(exist_ok=True)

    train = pd.read_csv(RAW_DIR / 'Train.csv')
    test = pd.read_csv(RAW_DIR / 'Test.csv')

    clean_train = clean_wind_dataset(train)
    clean_test = clean_wind_dataset(test)

    daily = clean_train.groupby(['Location', 'date'], as_index=False).agg(
        avg_power=('Power', 'mean'),
        max_power=('Power', 'max'),
        avg_wind_speed_100m=('WS_100m', 'mean'),
        avg_wind_speed_10m=('WS_10m', 'mean'),
        avg_temperature_2m=('Temp_2m', 'mean'),
        avg_relative_humidity_2m=('RelHum_2m', 'mean'),
        avg_wind_gust_10m=('WG_10m', 'mean')
    )

    monthly = clean_train.groupby(['Location', 'year', 'month'], as_index=False).agg(
        avg_power=('Power', 'mean'),
        avg_wind_speed_100m=('WS_100m', 'mean'),
        avg_wind_speed_10m=('WS_10m', 'mean'),
        avg_temperature_2m=('Temp_2m', 'mean'),
        reading_count=('Power', 'size')
    )

    clean_train.to_csv(OUT_DIR / 'wind_turbine_train_clean.csv', index=False)
    clean_test.to_csv(OUT_DIR / 'wind_turbine_test_clean.csv', index=False)
    daily.to_csv(OUT_DIR / 'wind_turbine_daily_summary.csv', index=False)
    monthly.to_csv(OUT_DIR / 'wind_turbine_monthly_summary.csv', index=False)

    return [clean_train, clean_test, daily, monthly]