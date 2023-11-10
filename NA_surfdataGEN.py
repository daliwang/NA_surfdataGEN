import netCDF4 as nc
from scipy.interpolate import griddata
import numpy as np
import pandas as pd 
from time import process_time
#from memory_profiler import profile

Points_in_land = "DataConversion_info/original_points_index.csv"

# Only wariables listed will be processed

# nearest neighbor:"double" variables
Variable_nearest = ['SLOPE', 'TOPO', 'PCT_GLACIER', 'PCT_LAKE', 'STD_ELEV']
# nearest neighbor:"int" variables
Variable_nearest += ['PFTDATA_MASK','SOIL_COLOR', 'SOIL_ORDER', 'abm']
# nearest neighbor:"double" variables (added 11/07/22023)
Variable_nearest += ['EF1_BTR', 'EF1_CRP', 'EF1_FDT', 'EF1_FET', 'EF1_GRS', 'EF1_SHR']

# nearest neighbor: "double" variables (added 11/10/2023)
Variable_nearest += ['PCT_SAND', 'PCT_CLAY','ORGANIC' ,'PCT_NAT_PFT', 
        'MONTHLY_LAI', 'MONTHLY_SAI' ,'MONTHLY_HEIGHT_TOP', 'MONTHLY_HEIGHT_BOT']

# nearest neighbor:"int" variables (gridcell)
Variable_urban_nearest = ['URBAN_REGION_ID']

# nearest neighbor:"int" variables (numurbl, gridcell)
Variable_urban_nearest += ['NLEV_IMPROAD' ]

# nearest neighbor:"double" variables (numurbl, gridcell)
Variable_urban_nearest += ['T_BUILDING_MAX', 'T_BUILDING_MIN',
        'WIND_HGT_CANYON','WTLUNIT_ROOF','WTROAD_PERV','THICK_ROOF',
        'THICK_WALL','PCT_URBAN','HT_ROOF','EM_IMPROAD','EM_PERROAD',
        'EM_ROOF','EM_WALL','CANYON_HWR']

# nearest neighbor:"double" variables (nlevurb, numurbl, gridcell)
Variable_urban_nearest += ['TK_IMPROAD','TK_ROOF','TK_WALL', 
                                 'CV_IMPROAD', 'CV_ROOF', 'CV_WALL']

# nearest neighbor:"double" variables (numrad, numurbl, gridcell)
Variable_urban_nearest += ['ALB_IMPROAD_DIF','ALB_IMPROAD_DIR','ALB_PERROAD_DIF',
        'ALB_PERROAD_DIR','ALB_ROOF_DIF', 'ALB_ROOF_DIR',
        'ALB_WALL_DIF', 'ALB_WALL_DIR']

Variable_nearest += Variable_urban_nearest

# linear intrepolation of "double" variables
Variable_linear = ['FMAX', 'Ws', 'ZWT0', 'binfl', 'gdp', 
                'peatf', 'Ds', 'Dsmax', 'F0', 'LAKEDEPTH',
               'LANDFRAC_PFT','P3', 'PCT_NATVEG', 'PCT_WETLAND', 
                'SECONDARY_P', 'OCCLUDED_P', 'LABILE_P']

# linear:"double" variables (added 11/07/22023)
Variable_linear += ['APATITE_P', 'PCT_CROP']

# Open the source file
src = nc.Dataset('surfdata.nc', 'r')

# Create a new file
dst = nc.Dataset('hr_surfdata.nc', 'w')

# Create new dimensions
#dst.createDimension('x_dim', 7814)
#dst.createDimension('y_dim', 8075)

# Copy dimensions
for name, dimension in src.dimensions.items():
    dst.createDimension(
        name, (len(dimension) if not dimension.isunlimited() else None))

# Copy global attributes
dst.setncatts(src.__dict__)

# get the fine resolution data and the locations (lat, lon)
r_daymet = nc.Dataset('TBOT.201401.nc', 'r', format='NETCDF4')
x_dim = r_daymet['x']  # 1D x-axis
y_dim = r_daymet['y']  # 1D y-axis
TBOT = r_daymet.variables['TBOT'][0,:,:]

# setup the bool_mask and XY mesh of the Daymet domain
bool_mask = ~np.isnan(TBOT)
grid_x, grid_y = np.meshgrid(x_dim,y_dim)
grid_y1 = grid_y[bool_mask]
grid_x1 = grid_x[bool_mask]

print(TBOT.shape,bool_mask.shape, grid_x.shape, grid_x1.shape)
# need to move into the loop
#data = np.zeros((len(y_dim),len(x_dim)), dtype=variable.datatype)
#f_data = np.ma.array(data, mask=bool_mask)
#f_data1 = f_data[bool_mask]

# the X, Y of the points (GCS_WGS_84)in 
# read in the points within daymet land mask
df= pd.read_csv(Points_in_land, header=0)
points_in_daymet_land = df.values.tolist()

# prepare the data source with points_in_daymet_land
# we use (Y, X) coordinates instead (lat,lon) for efficient interpolation
land_points = len(points_in_daymet_land)
points=np.zeros((land_points, 2), dtype='double')
for i in range(land_points):
    # points = [y,x] coordinates for 
    points[i,0] = points_in_daymet_land[i][1]
    points[i,1] = points_in_daymet_land[i][0]

# Create new dimensions
dst.createDimension('x_dim', x_dim.size)
dst.createDimension('y_dim', y_dim.size)

# Copy variables
for name, variable in src.variables.items():
    start = process_time()
    print("Working on varibale: "+ name + " dimensions: " + str(variable.dimensions))
    
    # Check if the last two dimensions are lsmlat and lsmlon
    if (variable.dimensions[-2:] == ('lsmlat', 'lsmlon')):
        # Determine the interpolation method
        if name in Variable_nearest:
            iMethod = 'nearest'
        elif name in Variable_linear:
            iMethod = 'linear'
        else:
            continue    # Skip all variables that are included in the variable lists

        # create variables with the new dimensions
        x = dst.createVariable(name, variable.datatype, variable.dimensions[:-2]+ ('y_dim', 'x_dim'))
        # Copy variable attributes
        dst[name].setncatts(src[name].__dict__)
        
        # prepare the array for the interpolated result
        f_data = np.ma.array(np.zeros((len(y_dim),len(x_dim)), dtype=variable.datatype), mask=bool_mask)
        #data = np.zeros((len(y_dim),len(x_dim)), dtype=variable.datatype)
        #f_data = np.ma.array(data, mask=bool_mask)
        f_data1 = f_data[bool_mask]
        print(name, f_data1.shape, f_data.shape, f_data.mask.shape, bool_mask.shape)  

        # Interpolate the variable
        o_data=np.zeros(land_points, dtype=variable.datatype)
         
        # Handle variables with two dimensions
        if (len(variable.dimensions) == 2):
            source = src[name][:]
            for i in range(land_points):
                # source is in [lat, lon] format
                o_data[i] = source[int(points_in_daymet_land[i][4]),int(points_in_daymet_land[i][5])]
              
            f_data1 = griddata(points, o_data, (grid_y1, grid_x1), method=iMethod)
            print(name, o_data[0:5], f_data1[0:5], f_data1.shape, f_data.shape)    
            # put the masked data back to the data (with the daymet land mask)
            f_data[bool_mask]=f_data1   

            # Assign the interpolated data
            dst[name][:] = f_data

        # Handle variables with three dimensions
        if (len(variable.dimensions) == 3):
            for index in range(variable.shape[0]):
                # get all the source data (global)
                source = src[name][index,:,:]
                for i in range(land_points):
                     # source is in [lat, lon] format
                      o_data[i] = source[int(points_in_daymet_land[i][4]),int(points_in_daymet_land[i][5])]
                f_data1 = griddata(points, o_data, (grid_y1, grid_x1), method=iMethod)

                # put the masked data back to the data (with the daymet land mask)
                f_data[bool_mask]=f_data1
                dst[name][index, :, :] = f_data
                print(name, index, o_data[0:5], f_data1[0:5], f_data1.shape, f_data.shape)  

        # Handle variables with four dimensions
        if (len(variable.dimensions) == 4):
            for index1 in range(variable.shape[0]):
                for index2 in range(variable.shape[1]):
                    # get all the source data (global)

                    source = src[name][index1, index2,:, :]
                    for i in range(land_points):
                        # source is in [lat, lon] format
                          o_data[i] = source[int(points_in_daymet_land[i][4]),int(points_in_daymet_land[i][5])]
                    f_data1 = griddata(points, o_data, (grid_y1, grid_x1), method=iMethod)

                    # put the masked data back to the data (with the daymet land mask)
                    f_data[bool_mask]=f_data1

                    dst[name][index1,index2,:,:] = f_data
                    print(name, index1, index2, o_data[0:5], f_data1[0:5], f_data1.shape, f_data.shape)         

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
        

# Close the files
src.close()
dst.close()