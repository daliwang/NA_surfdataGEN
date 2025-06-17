import os
import numpy as np
from netCDF4 import Dataset

input_file = 'ELM_PFT_output/combined_pft_count.nc'
output_file = 'ELM_PFT_output/pft_total_count_percentage.nc'

# Load all variables from the combined file
with Dataset(input_file, 'r') as nc:
    pft_count_vars = {var: nc.variables[var][:] for var in nc.variables if var.endswith('_count')}
    print("Loaded variables:", list(pft_count_vars.keys()))

# Calculate total count
pft_total_count = np.zeros_like(next(iter(pft_count_vars.values())), dtype=np.int16)
for arr in pft_count_vars.values():
    pft_total_count += arr

# Calculate percentage for each PFT, set np.nan where total count is negative
pft_percentage_vars = {}
for var_name, arr in pft_count_vars.items():
    with np.errstate(divide='ignore', invalid='ignore'):
        pct = np.where(pft_total_count > 0, (arr / pft_total_count) * 100.0, np.nan)
        pct = np.where(pft_total_count < 0, np.nan, pct)  # Force np.nan for negative total count
    pft_percentage_vars[var_name.replace('_count', '_percentage')] = pct.astype(np.float32)

# Save total count as well
pft_percentage_vars['pft_total_count'] = pft_total_count.astype(np.int16)

# Write to NetCDF
os.makedirs(os.path.dirname(output_file), exist_ok=True)
with Dataset(output_file, 'w', format='NETCDF4') as nc:
    # Use the shape of the arrays for dimensions
    nfiles, ny, nx = pft_total_count.shape
    nc.createDimension('file', nfiles)
    nc.createDimension('y', ny)
    nc.createDimension('x', nx)
    for var_name, arr in pft_percentage_vars.items():
        dtype = arr.dtype
        var = nc.createVariable(var_name, dtype, ('file', 'y', 'x'), zlib=True, complevel=5, fill_value=np.nan if np.issubdtype(dtype, np.floating) else -9999)
        var[:, :, :] = arr
        var.long_name = f"{var_name} from all pft*.nc files"
        print(f"Saved {var_name} with shape {arr.shape}")

print(f"Combined PFT percentage variables saved to {output_file}")