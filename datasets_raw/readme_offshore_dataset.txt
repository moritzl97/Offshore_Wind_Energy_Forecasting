The data in this repository consists of 4 files. This includes a readme file [readme.txt], a file summarizing the wind speed [All_Windspeed_Data.csv], a for the resulting power outputs [All_Power_Data.csv], 
and a zip-file including detailed data for each wind farm [Data_Per_Wind_Farm.zip]. Each file can be downloaded seperatly or colectivly by clicking the "Download all"-Button.

The structure of this repository is as follows:

├── readme.txt (this file)

├── All_Power_Data.csv (Power time series of wind farms)

├── All_Windspeed_Data.csv (Windspeed time series of wind farms)

├── Data_Per_Wind_Farm (folder including csv-files for each wind farm)
          ├── Baie_de_Saint_Brieuc 
          ├── Baltic_Eagle
          ├── Beatrice
          ├── Borkum_Riffgrund
          ├── Borssele_(Phase_1,2)
          ├── Borssele_(Phase_3,4)
          ├── Dieppe_et_Le_Treport
          ├── Dogger_Bank_(Phase_A,B)
          ├── East_Anglia_One
          ├── Gemini
          ├── Gode_Wind
          ├── Greater_Gabbard
          ├── Gwynt_y_Mor
          ├── Hautes_Falaises
          ├── Hohe_See
          ├── Hollandse_Kust_Noord
          ├── Hollandse_Kust_Zuid
          ├── Horns_Rev
          ├── Hornsea_(Project_1)
          ├── Hornsea_(Project_2)
          ├── Iles_dYeu_et_de_Noirmoutir
          ├── Kriegers_Flak
          ├── London_Array
          ├── Moray_Firth
          ├── Race_Bank
          ├── Seagreen
          ├── Seamade
          ├── Triton_Knoll
          ├── Walney




In the 29 files included in the zip-file [Data_Per_Wind_Farm.zip], we report detailed data for each wind farm. Therein, each column includs one variable while each row represents one point in time. 
Namely, the columns contain:
- time
- u-component of wind 100m above ground
- v-component of wind 100m above ground
- forecasted surface roughness (fsr)
- scaled windspeed at hub heigts (heigt given in parentheses - multiple time series possible)
- Wind direction in degrees
- Power of wind turbines (type given in parentheses - multiple time series possible)
- Turn_off (0: turbine turned off because of strong winds, 1: turbines active)
- Power (resulting power output of wind farm over all turbine types).

Starting from January 1, 1980, 00:00 am UTC in the first row, the data set ranges up to December 31, 2019, 11:00 pm
in the last of 350640 rows. 

Similar to the detailed files per wind farm, each row in the two csv files [All_Power_Data.csv , All_Windspeed_Data.csv] reporting wind speed at hub height and total power represent one point in time for the same period.
In the [All_Power_Data.csv] each row gives the sythetic resulting power outout of one wind farm. I.e., the dataset includes 29 columns one for each wind farm. 
In the [All_Windspeed_Data.csv] each row gives the calculated windspeed im 100m above ground at the position of each wind farm. I.e., the dataset includes 29 columns one for each wind farm. 

Data generated using Copernicus Climate Change Service information [1980-2019] and containing modified Copernicus Climate Change Service information [1980-2019].