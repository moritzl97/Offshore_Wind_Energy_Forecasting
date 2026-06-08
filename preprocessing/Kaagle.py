import pandas as pd

def Kaagle():

    df_scada = pd.read_csv("../datasets_raw/T1.csv")

    # Unifying time format part of PB-2
    # Noe becomes a cleaner standard format

    df_scada['Date/Time'] = pd.to_datetime(df_scada['Date/Time'], format='%d %m %Y %H:%M')

    # Flag zero power rows
    # True = the turbine produced zero power at that moment
    # False = the turbine was producing normally
    df_scada['zero_power'] = df_scada['LV ActivePower (kW)'] == 0

    # Keep the one that are True
    df_scada = df_scada[df_scada['LV ActivePower (kW)'] >= 0]

    # Set Date/Time as the index first
    df_scada = df_scada.set_index('Date/Time')

    # We moved the timestamp column from a regular column to the index of the dataframe. This is required for resampling
    # Pandas needs the time to be the index so it knows how to group the rows by hour.

    # Resample to hourly using mean
    df_scada_hourly = df_scada.resample('1h').agg({
        'LV ActivePower (kW)': 'mean',
        'Wind Speed (m/s)': 'mean',
        'Theoretical_Power_Curve (KWh)': 'mean',
        'Wind Direction (°)': 'mean',
        'zero_power': 'sum'  # Counts how many zero power readings were in that hour
    })

    # This grouped all 10-minute rows that belong to the same hour together and calculated the mean of each column within that hour.
    # So for example the 6 rows between 00:00 and 00:50 became one single row at 00:00.
    # For zero_power specifically we used sum instead of mean
    # So it tells us how many of the 6 ten-minute readings within that hour had zero power, which is more useful than an average.

    # Cell 11 - Convert kW to MW
    df_scada_hourly['LV ActivePower (MW)'] = df_scada_hourly['LV ActivePower (kW)'] / 1000
    df_scada_hourly['Theoretical_Power_Curve (MW)'] = df_scada_hourly['Theoretical_Power_Curve (KWh)'] / 1000

    return df_scada_hourly