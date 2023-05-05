import netCDF4 as nc
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import os
from pathlib import Path
from time import process_time
from memory_profiler import profile

save = 1
list =1

start0 = process_time()
# nearest neighbor:"double" variables
#Variable_nn_double = ['SLOPE']
Variable_nn_double = ['SLOPE', 'TOPO', 'PCT_GLACIER', 'PCT_LAKE', 'STD_ELEV']

# nearest neighbor:"int" variables
Variable_nn_int = ['PFTDATA_MASK','SOIL_COLOR', 'SOIL_ORDER', 'abm']

# linear intrepolation of "double" variables
#Variable_in_double = ['FMAX']
Variable_in_double = ['FMAX', 'Ws', 'ZWT0', 'binfl', 'gdp', 
                'peatf', 'Ds', 'Dsmax', 'F0', 'LAKEDEPTH',
               'LANDFRAC_PFT','P3', 'PCT_NATVEG', 'PCT_WETLAND', 
                'SECONDARY_P', 'OCCLUDED_P', 'LABILE_P']

Variable_type = ['double', 'int32']
Method_list = ['nearest', 'linear', 'cubic', 'gk']
Dimension_list = ['gridcell', 'nlevsoi', 'natpft',
                  'numburbl', 'ulevurb', 'numrad' ]

'''
====== linear =====
double     Ws(gridcell) "
double   ZWT0(gridcell) "
double  binfl(gridcell) "
double    gdp(gridcell) "
double  peatf(gridcell) "

double          Ds(gridcell) "
double       Dsmax(gridcell) "
double          F0(gridcell) "
double        FMAX(gridcell) "
double   LAKEDEPTH(gridcell) "
double          P3(gridcell) "
double  PCT_NATVEG(gridcell) "
double PCT_WETLAND(gridcell) ""

double SECONDARY_P(gridcell) "
double  OCCLUDED_P(gridcell) "
double    LABILE_P(gridcell) "

======nearest neighbor======
double PCT_GLACIER(gridcell) 
double    PCT_LAKE(gridcell) 
double    STD_ELEV(gridcell) 
double       SLOPE(gridcell)
double        TOPO(gridcell) 

int PFTDATA_MASK(gridcell) 
int  SOIL_COLOR(gridcell) 
int  SOIL_ORDER(gridcell) 
int         abm(gridcell) 

'''

# double variable with nearest neighbor method
if list ==1:
    iMethod = Method_list[0]  # 0 nearest
    iVariable_list = Variable_nn_double
    iVariable_type = Variable_type[0] # 0: Double, 1: int32

# int variable with nearest neighbor method
if list ==2:
    iMethod = Method_list[0]  # 0 nearest
    iVariable_list = Variable_nn_int
    iVariable_type = Variable_type[1] # 0: Double, 1: int32

# double variable with linear interpolation method
if list ==3:
    iMethod = Method_list[1]  # 0 linear
    iVariable_list = Variable_in_double
    iVariable_type = Variable_type[0] # 0: Double, 1: int32

Points_in_land = "DataConversion_info/original_points_index.csv"
outputfile = 'surface_properities_1kmx1km_'+iVariable_type+'_'+iMethod+'.nc'

if Path(outputfile).exists():
    os.remove(outputfile)
if save:
    # Open a new NetCDF file to write the data to. For format, you can choose from
    # 'NETCDF3_CLASSIC', 'NETCDF3_64BIT', 'NETCDF4_CLASSIC', and 'NETCDF4'
    w_nc_fid = nc.Dataset(outputfile, 'w', format='NETCDF4')
    w_nc_fid.title = 'The 1kmx1km surface propertties derived from a 0.5 degree global dataset'

start = process_time()
# get the fine resolution data and the locations (lat, lon)
r_daymet = nc.Dataset('Daymet_FSDS.nc', 'r', format='NETCDF4')
x_coor = r_daymet.variables['x'][:]  # 1D x-axis
y_coor = r_daymet.variables['y'][:]  # 1D y-axis
FSDS = r_daymet.variables['FSDS'][0,:,:]

mask_d = np.where(~np.isnan(FSDS), 1, 0)
data = np.zeros((len(y_coor),len(x_coor)), dtype='double')
f_data = np.ma.array(data, mask=mask_d)
grid_x, grid_y = np.meshgrid(x_coor,y_coor)
grid_y1 = grid_y[f_data.mask]
grid_x1 = grid_x[f_data.mask]
f_data1 = f_data[f_data.mask]

end = process_time()
print("Settup masked Numpy array for Daymet Domain takes  {}".format(end-start))

if save:
    # create the dimension variable
    x_dim = w_nc_fid.createDimension('x_dim', len(x_coor))
    y_dim = w_nc_fid.createDimension('y_dim', len(y_coor))
    time_dim = w_nc_fid.createDimension('time_dim', 1)

# read in the points within daymet land mask
start = process_time()
df= pd.read_csv(Points_in_land, header=0)
points_in_daymet_land = df.values.tolist()

# prepare the data source with points_in_daymet_land

land_points = len(points_in_daymet_land)
points=np.zeros((land_points, 2), dtype='double')
o_data=np.zeros(land_points, dtype='double')
for i in range(land_points):
    # points = [y,x]
    points[i,0] = points_in_daymet_land[i][1]
    points[i,1] = points_in_daymet_land[i][0]

end = process_time()
print("Reading the locations of source data points takes  {}".format(end-start))
    
# read in the source data
r_surf = nc.Dataset('surfdata.nc', 'r', format='NETCDF4')

for v in range(len(iVariable_list)):
    source = r_surf.variables[iVariable_list[v]][:]

    start = process_time() 
    for i in range(land_points):
        # source is in [lat, lon] format
        o_data[i] = source[int(points_in_daymet_land[i][4]),int(points_in_daymet_land[i][5])]
    points[0:5,:],o_data[0:5]
    
    end = process_time()
    print("Getting the source data (" + iVariable_list[v]+") ready takes  {}".format(end-start))

    start = process_time()
    f_data1 = griddata(points, o_data, (grid_y1, grid_x1), method=iMethod)
    end = process_time()
    print("griddata takes  {}".format(end-start))
    
    # put the masked data back to the data (with the daymet land mask)
    f_data = np.ma.array(data, mask=mask_d)
    f_data[f_data.mask]=f_data1
    
    end = process_time()
    print("Getting the interpolated data ready takes  {}".format(end-start))

    if save:
        w_nc_var = w_nc_fid.createVariable(iVariable_list[v], iVariable_type, ('y_dim','x_dim'))
        w_nc_var.long_name = iVariable_list[v]    
        w_nc_fid.variables[iVariable_list[v]][:] = f_data

if save:
    w_nc_fid.close()  # close the new file
    end = process_time()
    print("The entire processing takes  {}".format(end-start0))

