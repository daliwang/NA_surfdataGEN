import os
import numpy as np
import rasterio
from rasterio.enums import Resampling
from netCDF4 import Dataset

# Settings
mask_file = 'large_daymet_mask.tif'
input_nc_files = [
    'ELM_PFT_output/pft_total_count_percentage.nc',
    'ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.nc'
]
output_dir = 'ELM_PFT_output/tif_exports'
os.makedirs(output_dir, exist_ok=True)

# Read mask for georeference
with rasterio.open(mask_file) as src:
    mask = src.read(1)
    profile = src.profile
    height, width = mask.shape

nodata_value = -9999.0
profile.update(dtype='float32', count=1, nodata=nodata_value)

def export_variable_to_tif(var_arr, var_name, mask, profile, output_dir):
    # If 3D, take the first slice (assume shape [1, y, x])
    if var_arr.ndim == 3 and var_arr.shape[0] == 1:
        var_arr = var_arr[0]
    # Resize if needed
    if var_arr.shape != mask.shape:
        with rasterio.MemoryFile() as memfile:
            temp_profile = profile.copy()
            temp_profile.update(count=1, dtype='float32')
            with memfile.open(**temp_profile) as temp_dst:
                temp_dst.write(var_arr.astype('float32'), 1)
                var_arr = temp_dst.read(
                    1,
                    out_shape=mask.shape,
                    resampling=Resampling.bilinear
                )
    # Mask out non-land
    var_arr_masked = np.where(mask == 1, var_arr, np.nan)
    # Save as GeoTIFF
    to_write = np.where(np.isnan(var_arr_masked), nodata_value, var_arr_masked)
    out_tif = os.path.join(output_dir, f"{var_name}.tif")
    with rasterio.open(out_tif, 'w', **profile) as dst:
        dst.write(to_write.astype('float32'), 1)
    print(f"Saved {out_tif}")

for nc_file in input_nc_files:
    with Dataset(nc_file, 'r') as nc:
        for var_name in nc.variables:
            # Only export percentage or fraction variables
            if any(key in var_name for key in ['percentage', 'fraction']):
                print(f"Processing {var_name} from {nc_file}")
                var_arr = nc.variables[var_name][:]
                export_variable_to_tif(var_arr, var_name, mask, profile, output_dir)