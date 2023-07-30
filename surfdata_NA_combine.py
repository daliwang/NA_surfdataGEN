import sys
sys.path.append('/home/7xw/ELM_ECP/lib/python3.8/site-packages/')

import os
import netCDF4 as nc

# Define dictionaries to store dimensions, variables, and attributes
combined_dims = {}
combined_vars = {}
combined_attrs = {}

input_path = '/home/7xw/ELM_ECP/ECPcode_py/HR_data_temp/'
input_file_list = ['surface_properities_1kmx1km_double_linear.nc']

output_file = input_path + 'outputdata1.nc'
if os.path.exists(output_file):
    os.remove(output_file)

# Set the input directory
input_file_dir = "/home/7xw/ELM_ECP/ECPcode_py/HR_data/urban"

# Find all NetCDF files in the input directory
netcdf_files = [f for f in os.listdir(input_file_dir) if f.endswith(".nc")]

for file_name in netcdf_files:
    # Open the file
    filename = os.path.join(input_file_dir, file_name)
    
    print("Processing file: "+filename)
    nc_frag = nc.Dataset(filename, 'r')
    nc_dims = nc_frag.dimensions
    nc_vars = nc_frag.variables
    
    # Loop over all the variables in the netCDF file
    for var_name, var in nc_frag.variables.items():
        # Get the variable's shape
        dimensions = var.dimensions
        
        # Get the variable's data type
        var_type = var.dtype
        
        # Save the variable information in the dictionary
        combined_vars[var_name] = {'dimensions': dimensions, 'type': var_type}
        
        # Copy variable data
        combined_vars[var_name]['data'] = var[:]
    
    for dim in nc_dims:
        if dim not in combined_dims:
            combined_dims[dim] = nc_dims[dim].size
    
    # Copy attributes
    for attr_name in nc_frag.ncattrs():
        combined_attrs[attr_name] = nc_frag.getncattr(attr_name)
    
    nc_frag.close()

# Check if the output file already exists and delete it if it does

# Create a new netCDF file
nc_combined = nc.Dataset(output_file, 'w')

# Create dimensions in the new netCDF dataset
for dim, size in combined_dims.items():
    nc_combined.createDimension(dim, size)

# Copy all variables to the new netCDF dataset
for var_name, var_obj in combined_vars.items():
    var_new = nc_combined.createVariable(var_name, var_obj['type'], var_obj['dimensions'])
    var_new[:] = var_obj['data']

# Copy attributes to the new netCDF dataset
for attr_name, attr_value in combined_attrs.items():
    setattr(nc_combined, attr_name, attr_value)

nc_combined.close()

print("Variable List:")
for var_name, var_obj in combined_vars.items():
    print(var_name, var_obj['type'], var_obj['dimensions']
            )
