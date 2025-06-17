import numpy as np
import rasterio
from netCDF4 import Dataset

# Open the aligned temperature NetCDF file
with Dataset('aligned_temp_to_large_nalcms_mask.nc') as nc:
    avg_temp = nc.variables['AvgTemp'][:]
    print(f"maximum AvgTemp: {np.max(avg_temp)}")
    print(f"shape of AvgTemp: {avg_temp.shape}")

# Define the output GeoTIFF file
output_tif = 'ELM_PFT_output/AvgTemp_in_large_daymet_mask.tif'

# Use the profile from large_daymet_mask.tif
input_tif = 'large_daymet_mask.tif'
with rasterio.open(input_tif) as src:
    profile = src.profile
    print(f"Profile of input GeoTIFF: {profile}")

# Flip vertically to match the GeoTIFF orientation (uncomment if needed)
# avg_temp = np.flipud(avg_temp)

# Ensure the data type is float32 and set nodata value
avg_temp = avg_temp.astype('float32')
nodata_value = -9999.0
profile.update(dtype='float32', nodata=nodata_value)

# Replace np.nan with nodata value
avg_temp = np.where(np.isnan(avg_temp), nodata_value, avg_temp)

# Write the output GeoTIFF
with rasterio.open(output_tif, 'w', **profile) as dst:
    dst.write(avg_temp, 1)

print(f"Saved aligned temperature data as {output_tif}")