import numpy as np
from netCDF4 import Dataset

# List of all landtype files and their PFT mapping
# For split: provide pft_names (list of 2), bounds (tuple), and set 'split' True
# For direct: provide pft_names (list of 1), set 'split' False
landtype_pft_map = [
    # Format: (input_file, pft_names, split, bounds)
    # Needleleaf (split)
    ('landtype1_nalcms_Temperate_needleleaf_in_daymet.nc', ['pft1', 'pft2'], True, (-19, -2)),
    # Taiga needleleaf (direct)
    ('landtype2_nalcms_Taiga_needleleaf_in_daymet.nc', ['pft2'], False, None),
    # Tropical evergreen (direct)
    ('landtype3_nalcms_Tropical_evergreen_in_daymet.nc', ['pft4'], False, None),
    # Tropical deciduous (direct)
    ('landtype4_nalcms_Tropical_deciduous_in_daymet.nc', ['pft6'], False, None),
    # Temperate deciduous (split)
    ('landtype5_nalcms_Temperate_deciduous_in_daymet.nc', ['pft7', 'pft8'], True, (-15, 5)),
    # Mixed forest (split)
    ('landtype6_nalcms_Mixed_forrest_in_daymet.nc', ['pft7', 'pft8'], True, (-19, 5)),
    # Tropical shrub (direct)
    ('landtype7_nalcms_Tropical_shrub_in_daymet.nc', ['pft9'], False, None),
    # Temperate shrub (split)
    ('landtype8_nalcms_Temperate_shrub_in_daymet.nc', ['pft10', 'pft11'], True, (-15, 5)),
    # Tropical grass (direct)
    ('landtype9_nalcms_Tropical_grass_in_daymet.nc', ['pft14'], False, None),
    # Temperate grass (split, but bounds are the same, so only two masks)
    ('landtype10_nalcms_Temperate_grass_in_daymet.nc', ['pft12', 'pft13'], True, (-19, -19)),
    # Polar shrub moss (direct)
    ('landtype11_nalcms_Polar_shrub_moss_in_daymet.nc', ['pft11'], False, None),
    # Polar grass moss (direct)
    ('landtype12_nalcms_Polar_grass_moss_in_daymet.nc', ['pft12'], False, None),
    # Polar barren moss (direct)
    ('landtype13_nalcms_Polar_barren_moss_in_daymet.nc', ['pft12'], False, None),
    # Wetland (direct)
    ('landtype14_nalcms_Wetland_in_daymet.nc', ['pft13'], False, None),
    # Cropland (direct)
    ('landtype15_nalcms_Cropland_in_daymet.nc', ['pft15'], False, None),
    # Barren land (direct)
    ('landtype16_nalcms_Barren_land_in_daymet.nc', ['pft0'], False, None),
    # Urban (direct)
    ('landtype17_nalcms_Urban_in_daymet.nc', ['urban'], False, None),
    # Water (direct)
    ('landtype18_nalcms_Water_in_daymet.nc', ['lake'], False, None),
    # Snow/Ice (direct)
    ('landtype19_nalcms_Snow_Ice_in_daymet.nc', ['pft0'], False, None),
]

# Path to aligned temperature file (used for all splits)
aligned_temp_file = 'aligned_temp_to_large_nalcms_mask.nc'

def create_pft_nc(input_file, pft_names, split, bounds, aligned_temp_file):
    # Load count
    with Dataset(f'../landtypes_count/{input_file}') as nc:
        count = nc.variables['landtype_count'][:]
    shape = count.shape

    if not split:
        # Assign all count to the single PFT
        pft = np.zeros_like(count, dtype=int)
        pft[:] = count
        output_file = f'{pft_names[0]}_{input_file}'
        output_file = f'ELM_PFT_output/{output_file}'
        with Dataset(output_file, 'w', format='NETCDF4') as dst:
            dst.createDimension('y', shape[0])
            dst.createDimension('x', shape[1])
            var = dst.createVariable(f'{pft_names[0]}_count', 'i4', ('y', 'x'), zlib=True, complevel=5)
            var[:, :] = pft
            var.long_name = f'{pft_names[0]} count based on {input_file}'
            var.units = "count"
            dst.setncattr('original_landtype_file', input_file)
        print(f"Saved {output_file}")
    else:
        # Split by temperature
        with Dataset(aligned_temp_file) as nc:
            avg_temp = nc.variables['AvgTemp'][:]
        lower, upper = bounds
        valid = (~np.isnan(avg_temp)) & (count >= 0)
        pftA = np.zeros_like(count, dtype=int)
        pftB = np.zeros_like(count, dtype=int)
        mask1 = valid & (avg_temp <= lower)
        mask2 = valid & (avg_temp > upper)
        mask_between = valid & (avg_temp > lower) & (avg_temp <= upper)
        # Assign values
        pftB[mask1] = count[mask1]
        pftA[mask2] = count[mask2]
        if lower != upper:
            frac = (avg_temp[mask_between] - lower) / (upper - lower)
            pftA[mask_between] = (count[mask_between] * frac).astype(int)
            pftB[mask_between] = count[mask_between] - pftA[mask_between]
        output_file = f"{'-'.join(pft_names)}_{input_file}"
        # I want to save the file in a sepearate directory
        output_file = f'ELM_PFT_output/{output_file}'

        with Dataset(output_file, 'w', format='NETCDF4') as dst:
            dst.createDimension('y', shape[0])
            dst.createDimension('x', shape[1])
            varA = dst.createVariable(f'{pft_names[0]}_count', 'i4', ('y', 'x'), zlib=True, complevel=5)
            varA[:, :] = pftA
            varA.long_name = f'{pft_names[0]} count based on AvgTemp'
            varA.units = "count"
            varB = dst.createVariable(f'{pft_names[1]}_count', 'i4', ('y', 'x'), zlib=True, complevel=5)
            varB[:, :] = pftB
            varB.long_name = f'{pft_names[1]} count based on AvgTemp'
            varB.units = "count"
            avg_temp_var = dst.createVariable('AvgTemp', 'f4', ('y', 'x'), fill_value=np.nan, zlib=True, complevel=5)
            avg_temp_var[:, :] = avg_temp
            avg_temp_var.long_name = "Average temperature of coldest month (aligned to large mask)"
            avg_temp_var.units = "C"
            dst.setncattr('temperature_bounds', f'{pft_names[1]}: <= {lower} C, {pft_names[0]}: > {upper} C')
            dst.setncattr('original_landtype_file', input_file)
        print(f"Saved {output_file}")

# Run for all landtypes
for input_file, pft_names, split, bounds in landtype_pft_map:
    create_pft_nc(input_file, pft_names, split, bounds, aligned_temp_file)