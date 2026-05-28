Source: WINS50 — KNMI/Whiffle HARMONIE-AROME offshore wind simulations
URL:    https://www.wins50.nl/data/

Files expected in this folder
------------------------------
wins50_harmonie_windfarm_powerproduction.zip
    One CSV per wind farm (161 farms, full North Sea).
    Columns: DateTime (YYYYMMDDHH), Power W20 [MW], Power W50 [MW]
    - W20 = 2020 operational scenario (NaN for farms not yet built)
    - W50 = hypothetical 2050 full build-out scenario
    Download: https://www.wins50.nl/downloads/wins50_harmonie_windfarm_powerproduction.zip

wins50_windfarm_scenarios.shp  (+ .dbf / .shx / .cpg)
    Shapefile with one polygon per farm per scenario.
    Attributes include installed capacity (MW), turbine type, hub height, country.
    Download: https://www.wins50.nl/downloads/wins50_windfarm_scenarios.zip

wins50_singlepoint_lookuptable.csv
    Maps every HARMONIE grid index (ix, iy) to lat/lon.
    Used to find the weather grid cell nearest each wind farm.
    Download: https://www.wins50.nl/downloads/wins50_singlepoint_lookuptable.csv

Note on wind-speed NetCDF files (needed for PB1-7 power curves)
----------------------------------------------------------------
The HARMONIE per-gridpoint time-series NetCDF files are NOT included here.
They require a free KNMI Open Data API key (register at https://developer.dataplatform.knmi.nl/).
See Section 7 of initial_exploration/initial_data_exploration_wins50.ipynb for the
download roadmap and a skeleton script.
Use wins50_farm_metadata.csv (in datasets/) to find grid_ix / grid_iy for each farm.
