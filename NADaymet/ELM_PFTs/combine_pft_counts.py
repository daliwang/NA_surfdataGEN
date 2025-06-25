import os
import numpy as np
import xarray as xr
from netCDF4 import Dataset

def extract_pft_variables(file_path):
    """Extract variables starting with 'pft' from a NetCDF file using xarray, omitting 'glacier'."""
    with xr.open_dataset(file_path) as ds:
        return {var: ds[var].values for var in ds.data_vars if var.startswith('pft') and var != 'glacier_count'}

def main():
    parent_dir = os.getcwd()
    output_dir = os.path.join(parent_dir, 'ELM_PFT_output')
    os.makedirs(output_dir, exist_ok=True)

    # Find all pft*.nc files
    pft_files = [f for f in os.listdir(parent_dir) if f.startswith('pft') and f.endswith('.nc')]
    if not pft_files:
        print("No pft*.nc files found in the current directory.")
        return

    # Extract and stack variables
    combined_vars = {}
    for pft_file in pft_files:
        pft_vars = extract_pft_variables(os.path.join(parent_dir, pft_file))
        for var_name, arr in pft_vars.items():
            # Omit glacier_count if present
            if var_name == 'glacier_count':
                continue
            combined_vars.setdefault(var_name, []).append(arr)
    for var_name in combined_vars:
        combined_vars[var_name] = np.stack(combined_vars[var_name], axis=0)

    # Mask out negative values
    fill_value = -1
    for var_name, arr in combined_vars.items():
        arr = np.where(arr < 0, fill_value, arr).astype(np.int16)
        combined_vars[var_name] = arr

    # Print summary
    for var_name, data in combined_vars.items():
        print(f"{var_name}: shape={data.shape}, dtype={data.dtype}, min={np.nanmin(data)}, max={np.nanmax(data)}, mean={np.nanmean(data):.2f}")

    # Combine all pft*_count arrays (with shape[0] > 1) into a total count
    pft_count_vars_combined = {}
    for var_name, arr in combined_vars.items():
        if var_name.endswith('_count'):
            if arr.shape[0] > 1:
                combined = arr.sum(axis=0, keepdims=True).astype(np.int16)
                pft_count_vars_combined[var_name] = combined
                print(f"{var_name} combined: shape={combined.shape}, min={combined.min()}, max={combined.max()}, mean={combined.mean():.2f}")
            else:
                pft_count_vars_combined[var_name] = arr
                print(f"{var_name}: shape={arr.shape}, min={arr.min()}, max={arr.max()}")

    # Save combined variables to NetCDF4
    output_file = os.path.join(output_dir, 'combined_pft_count.nc')
    with Dataset(output_file, 'w', format='NETCDF4') as nc:
        for var_name, arr in pft_count_vars_combined.items():
            nfiles, ny, nx = arr.shape
            # Create dimensions if they do not exist
            dim_name = f"{var_name}_file"
            for dim, size in zip([dim_name, 'y', 'x'], [nfiles, ny, nx]):
                if dim not in nc.dimensions:
                    nc.createDimension(dim, size)
            print(f"Saving {var_name} with shape {arr.shape}")
            var = nc.createVariable(var_name, 'i2', (dim_name, 'y', 'x'), zlib=True, complevel=5)
            var[:, :, :] = arr
            var.long_name = f"Combined {var_name} from all pft*.nc files"
            var.units = 'count'
            var.fill_value = fill_value
            var.standard_name = var_name
            var.comment = f"Combined from {len(pft_files)} files"

    #set global attributes
    with Dataset(output_file, 'a') as nc:
        nc.description = "Combined PFT count variables from multiple pft*.nc files"
        nc.description += " using negetive value (-1) as fillvalue for mask."
        nc.description += " The variables are combined by summing across the first dimension."
        nc.description += " The number of negative values indicates the number of files that were combined."
        nc.history = f"Created on {np.datetime64('now')}"
        nc.source = "ELM PFT output files"
        nc.Conventions = "CF-1.6"


    print(f"Combined PFT variables saved to {output_file}")

if __name__ == "__main__":
    main()