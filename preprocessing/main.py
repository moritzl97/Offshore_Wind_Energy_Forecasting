import numpy as np
from ENTSO_timeseries import ENTSO_timeseries
from Kaagle import Kaagle
from KNMI import KNMI
from Offshore_Wind_Farms import Offshore_wind_farm
from Wind_turbine_power import Wind_turbine_power

def main():

    print("-" * 50)

    try:
        print("Running ENTSO preprocessing")
        preprocess_ENTSO = ENTSO_timeseries()

        preprocess_ENTSO.to_csv("../datasets/ENTSOE_power_time_series.csv")

        print("ENTSO ran successfully")

    except Exception as e:
        print(f"ENTSO preprocessing failed {e}")

    print("-" * 50)

    try:
        print("Running Kaagle preprocessing")
        preprocess_Kaagle = Kaagle()

        preprocess_Kaagle.to_csv("'../datasets/scada_clean.csv'")

        print("Kaagle ran successfully")

    except Exception as e:
        print(f"Kaagle preprocessing failed {e}")

    print("-" * 50)

    try:
        print("Running KNMI preprocessing")
        preprocess_KNMI = KNMI()

        # File save in function

        print("KNMI ran successfully")
    except Exception as e:
        print(f"KNMI preprocessing failed {e}")

    print("-" * 50)

    try:
        print("Running Offshore wind farm")
        preprocess_Offshore = Offshore_wind_farm()

        # File save in function

        print("Offshore ran successfully")

    except Exception as e:
        print(f"Offshore wind farm failed {e}")

    print("-" * 50)

    try:
        print("Running Wind turbine power")
        preprocess_Wind_turbine = Wind_turbine_power()

        # File save in function

        print("Wind turbine ran successfully")

    except Exception as e:
        print(f"Wind turbine power failed {e}")

    print("-" * 50)

if __name__ == "__main__":
    main()