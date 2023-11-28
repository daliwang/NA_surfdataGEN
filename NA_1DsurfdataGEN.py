
# use 1D domain and 2D surfdat to generate 1D surfdata

import os 
import netCDF4 as nc
import numpy as np
from itertools import cycle
from time import process_time

from datetime import datetime

# Get current date
current_date = datetime.now()
# Format date to mmddyyyy
formatted_date = current_date.strftime('%m%d%Y')

def surfdata_save_1dNA(input_path, output_path, surfdata_file):

    # Open a new NetCDF file to write the data to. For format, you can choose from
    # 'NETCDF3_CLASSIC', 'NETCDF3_64BIT', 'NETCDF4_CLASSIC', and 'NETCDF4'
    src = nc.Dataset(surfdata_file, 'r', format='NETCDF4')

    outputfile = output_path + 'surfdata.Daymet4.1km.1d.nc'

    # Open a new NetCDF file to write the data to. For format, you can choose from
    # 'NETCDF3_CLASSIC', 'NETCDF3_64BIT', 'NETCDF4_CLASSIC', and 'NETCDF4'
    dst = nc.Dataset(outputfile, 'w', format='NETCDF4')
    dst.title = '1D surfdata generated from '+surfdata_file+ ' on '+formatted_date

    # first add gridID and gridcell from Daymet4.1km.1d.domain.nc
    domain_file = 'Daymet4.1km.1d.domain.nc'
    domain = nc.Dataset(domain_file, 'r', format='NETCDF4')

    # create gridcell dimension
    # Get the dimension from the domain file
    domain_dim = domain.dimensions['ni']

    # Create the dimension in the destination file
    dst.createDimension('gridcell', len(domain_dim) if not domain_dim.isunlimited() else None)

    # copy the gridID, xc, and yc
    variables_to_copy = ['gridIDs', 'xc', 'yc']  # replace with your variable names

    # Copy variables from domain to dst
    for name in variables_to_copy:
        if name in domain.variables and name not in dst.variables:
            variable = domain.variables[name]
            x = dst.createVariable(name, variable.datatype, 'gridcell')
            # Copy variable attributes
            dst[name].setncatts(domain[name].__dict__)
            dst[name][:] = domain[name][:]


    # Copy dimensions (execept x_dim and y_dim) from src (2D surfdata)
    for name, dimension in src.dimensions.items():
        if (name != 'x_dim' or name != 'y_dim'):
            dst.createDimension(
            name, (len(dimension) if not dimension.isunlimited() else None))

    # Copy global attributes
    dst.setncatts(src.__dict__)

    # copy variables from src (2D surfdata) 

#==========

    count = 0 # record how may 2D layers have been processed 

    #get the 2D domain mask
    data = src['SLOPE'][:]
    bool_mask = ~np.isnan(data)

    # Copy variables
    for name, variable in src.variables.items():
        start = process_time()
        print("Working on varibale: "+ name + " dimensions: " + str(variable.dimensions))
        
        # Check if the last two dimensions are lsmlat and lsmlon
        if (variable.dimensions[-2:] == ('y_dim', 'x_dim')):

            x = dst.createVariable(name, variable.datatype, variable.dimensions[:-2]+ ('gridcell',))
            # Copy variable attributes
            dst[name].setncatts(src[name].__dict__)
             
            # Handle variables with two dimensions
            if (len(variable.dimensions) == 2):
                source = src[name][:]
                f_data= np.copy(source[bool_mask]) 

                # Assign the interpolated data
                dst[name][:] = f_data
                print(name, f_data[0:5], f_data.shape)
                count = count + 1

            # Handle variables with three dimensions
            if (len(variable.dimensions) == 3):
                for index in range(variable.shape[0]):
                    # get all the source data (global)
                    source = src[name][index,:,:]
                    f_data= np.copy(source[bool_mask]) 

                    # Assign the interpolated data to dst.variable
                    dst[name][index,:] = f_data
                    print(name, index, f_data[0:5], f_data.shape)

                count = count + variable.shape[0]

            # Handle variables with four dimensions
            if (len(variable.dimensions) == 4):
                for index1 in range(variable.shape[0]):
                    for index2 in range(variable.shape[1]):
                        # get all the source data (global)

                        source = src[name][index1, index2,:, :]
                        f_data= np.copy(source[bool_mask]) 

                        # Assign the interpolated data to dst.variable
                        dst[name][index1,index2,:] = f_data
                        print(name, index1, index2, f_data[0:5], f_data.shape)

                    count = count + variable.shape[1]

            end = process_time()
            print("Generating variable: " +name+ " takes  {}".format(end-start))

        else:

            # keep variables with the same dimension
            x = dst.createVariable(name, variable.datatype, variable.dimensions)
            # Copy variable attributes
            dst[name].setncatts(src[name].__dict__)
            # Copy the data
            dst[name][:] = src[name][:]

            end = process_time()
            print("Copying variable: " +name+ " takes  {}".format(end-start))
            
        if count > 50:
            dst.close()   # output the variable into file to save memory

            dst = nc.Dataset(outputfile, 'a')

            count = 0

#==========

    src.close()  
    domain.close()
    dst.close()        

    
def main():
    """
    args = sys.argv[1:]
    input_path = args[0]
    output_path = args[1]
    number_of_subdomains = int(arg[2])
    i_timesteps = int(arg[3])
    """
    
    input_path= './'
    surfdata_file = 'Daymet4.1km.2D.surfdata_v1_part1.nc'
    output_path = input_path
 
    start = process_time() 
    surfdata_save_1dNA(input_path, output_path, surfdata_file)
    end = process_time()
    print("Saving 1D surfdata takes {}".format(end-start))

if __name__ == '__main__':
    main()
    