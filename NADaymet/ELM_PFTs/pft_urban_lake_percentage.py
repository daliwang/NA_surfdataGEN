import os
import numpy as np
from netCDF4 import Dataset

# Input files
pft_file = 'ELM_PFT_output/pft_total_count_percentage.nc'
urban_file = 'ELM_PFT_output/urban_landtype17_nalcms_Urban_in_daymet.nc'
lake_file = 'ELM_PFT_output/lake_landtype18_nalcms_Water_in_daymet.nc'

# Output file
output_file = 'ELM_PFT_output/combined_pft_urban_lake_total_count.nc'
os.makedirs(os.path.dirname(output_file), exist_ok=True)

# Load arrays
with Dataset(pft_file, 'r') as nc:
    pft_total_count = nc.variables['pft_total_count'][:]
    # If you have multiple pft*_count variables, sum them here instead:
    # pft_total_count = sum([nc.variables[v][:] for v in nc.variables if v.endswith('_count')])

with Dataset(urban_file, 'r') as nc:
    urban_arr = nc.variables['urban_count'][:]

with Dataset(lake_file, 'r') as nc:
    lake_arr = nc.variables['lake_count'][:]

# Compute total count
Total_count = pft_total_count + urban_arr + lake_arr

# Compute percentages, set np.nan where Total_count < 0 (non-land)
with np.errstate(divide='ignore', invalid='ignore'):
    pft_percentage = np.where(Total_count > 0, (pft_total_count / Total_count) * 100.0, np.nan)
    urban_percentage = np.where(Total_count > 0, (urban_arr / Total_count) * 100.0, np.nan)
    lake_percentage = np.where(Total_count > 0, (lake_arr / Total_count) * 100.0, np.nan)
    # Assign 100% for land fraction where Total_count >= 1089, else scale accordingly
    land_fraction = np.where(
        Total_count < 0, np.nan,  # non-land
        np.where(Total_count >= 1089, 100.0, (Total_count / 1156.0) * 100.0)
    )


    # Force np.nan for all percentages where Total_count < 0
    pft_percentage = np.where(Total_count < 0, np.nan, pft_percentage)
    urban_percentage = np.where(Total_count < 0, np.nan, urban_percentage)
    lake_percentage = np.where(Total_count < 0, np.nan, lake_percentage)
    land_fraction = np.where(Total_count < 0, np.nan, land_fraction)

# Save to NetCDF
nfiles, ny, nx = Total_count.shape
with Dataset(output_file, 'w', format='NETCDF4') as nc:
    nc.createDimension('file', nfiles)
    nc.createDimension('y', ny)
    nc.createDimension('x', nx)

    # Counts
    nc.createVariable('pft_total_count', 'i2', ('file', 'y', 'x'), zlib=True, complevel=5)[:] = pft_total_count
    nc.createVariable('urban_count', 'i2', ('file', 'y', 'x'), zlib=True, complevel=5)[:] = urban_arr
    nc.createVariable('lake_count', 'i2', ('file', 'y', 'x'), zlib=True, complevel=5)[:] = lake_arr
    nc.createVariable('total_count', 'i2', ('file', 'y', 'x'), zlib=True, complevel=5)[:] = Total_count

    # Percentages
    nc.createVariable('pft_percentage', 'f4', ('file', 'y', 'x'), zlib=True, complevel=5, fill_value=np.nan)[:] = pft_percentage
    nc.createVariable('urban_percentage', 'f4', ('file', 'y', 'x'), zlib=True, complevel=5, fill_value=np.nan)[:] = urban_percentage
    nc.createVariable('lake_percentage', 'f4', ('file', 'y', 'x'), zlib=True, complevel=5, fill_value=np.nan)[:] = lake_percentage
    nc.createVariable('land_fraction', 'f4', ('file', 'y', 'x'), zlib=True, complevel=5, fill_value=np.nan)[:] = land_fraction

print(f"Saved all counts and percentages to {output_file}")