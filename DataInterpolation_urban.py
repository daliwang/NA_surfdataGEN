##  Batched data filing with nearest neighbor interpolation
##  (urban, multiple-layer (gridcell) variables)
##  rerun to generate the new dataset with right numrad = 2 on July 29, 2023

import netCDF4 as nc
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import os
from pathlib import Path

save = 1
list = 1

numurbl = 3 ;
nlevurb = 5 ;
numrad = 2 ;
nlevsoi = 10 ;

time = 12
nchar = 256 ;
lsmpft = 17 ;
natpft = 17 ;

# nearest neighbor:"int" variables (gridcell)
Variable_urban_int_1D = ['URBAN_REGION_ID']

# nearest neighbor:"int" variables (numurbl, gridcell)
Variable_urban_int_2D = ['NLEV_IMPROAD' ]

# nearest neighbor:"double" variables (numurbl, gridcell)
Variable_urban_double_2D = ['T_BUILDING_MAX', 'T_BUILDING_MIN',
        'WIND_HGT_CANYON','WTLUNIT_ROOF','WTROAD_PERV','THICK_ROOF',
        'THICK_WALL','PCT_URBAN','HT_ROOF','EM_IMPROAD','EM_PERROAD',
        'EM_ROOF','EM_WALL','CANYON_HWR']

# nearest neighbor:"double" variables (nlevurb, numurbl, gridcell)
Variable_urban_double_3D_nlev = ['TK_IMPROAD','TK_ROOF','TK_WALL', 
                                 'CV_IMPROAD', 'CV_ROOF', 'CV_WALL']
#Variable_urban_double_3D_nlev = ['TK_IMPROAD']

# nearest neighbor:"double" variables (numrad, numurbl, gridcell)
Variable_urban_double_3D_nrad = ['ALB_IMPROAD_DIF','ALB_IMPROAD_DIR','ALB_PERROAD_DIF',
        'ALB_PERROAD_DIR','ALB_ROOF_DIF', 'ALB_ROOF_DIR',
        'ALB_WALL_DIF', 'ALB_WALL_DIR']
#Variable_urban_double_3D_nrad = ['ALB_IMPROAD_DIF']

Variable_type = ['double', 'int32']
Method_list = ['nearest', 'linear', 'cubic', 'gk']
Dimension_list = ['gridcell', 'nlevsoi', 'natpft',
                  'numburbl', 'ulevurb', 'numrad' ]

'''
===== multiple layers variable (non-urban, nearest neighbor) ====
double     ORGANIC(nlevsoi, gridcell)
double    PCT_CLAY(nlevsoi, gridcell)
double    PCT_SAND(nlevsoi, gridcell)

double PCT_NAT_PFT(natpft, gridcell) 


====== urban variables (nearest neighbor) ====

int    URBAN_REGION_ID(gridcell)

int       NLEV_IMPROAD(numurbl, gridcell) 

double  T_BUILDING_MAX(numurbl, gridcell) "
double  T_BUILDING_MIN(numurbl, gridcell) "
double WIND_HGT_CANYON(numurbl, gridcell) 
double    WTLUNIT_ROOF(numurbl, gridcell) "
double     WTROAD_PERV(numurbl, gridcell) "
double      THICK_ROOF(numurbl, gridcell) "
double      THICK_WALL(numurbl, gridcell) "
double       PCT_URBAN(numurbl, gridcell) 
double         HT_ROOF(numurbl, gridcell) 
double      EM_IMPROAD(numurbl, gridcell) "
double      EM_PERROAD(numurbl, gridcell) "
double         EM_ROOF(numurbl, gridcell) "
double         EM_WALL(numurbl, gridcell) "
double      CANYON_HWR(numurbl, gridcell)

double      TK_IMPROAD(nlevurb, numurbl, gridcell) "
double         TK_ROOF(nlevurb, numurbl, gridcell) "
double         TK_WALL(nlevurb, numurbl, gridcell) "
double      CV_IMPROAD(nlevurb, numurbl, gridcell) "
double         CV_ROOF(nlevurb, numurbl, gridcell) "
double         CV_WALL(nlevurb, numurbl, gridcell) "

double ALB_IMPROAD_DIF(numrad, numurbl, gridcell) 
double ALB_IMPROAD_DIR(numrad, numurbl, gridcell) "
double ALB_PERROAD_DIF(numrad, numurbl, gridcell) "
double ALB_PERROAD_DIR(numrad, numurbl, gridcell) "
double    ALB_ROOF_DIF(numrad, numurbl, gridcell) "
double    ALB_ROOF_DIR(numrad, numurbl, gridcell) "
double    ALB_WALL_DIF(numrad, numurbl, gridcell) "
double    ALB_WALL_DIR(numrad, numurbl, gridcell) "
'''

iMethod = Method_list[0]  # 0 nearest
# int variable with nearest neighbor method
if list==1: 
    tag = "int_y_x"
    iVariable_list = Variable_urban_int_1D 
    iVariable_type = Variable_type[1] # 0: Double, 1: int32

# int variable with nearest neighbor method (numurbl, gridcell))
if list == 2:
    tag = "int_numurbl_y_x"
    iVariable_list = Variable_urban_int_2D
    iVariable_type = Variable_type[1] # 0: Double, 1: int32
    
if list == 3:
    tag = "double_numurbl_y_x"
    iVariable_list = Variable_urban_double_2D
    iVariable_type = Variable_type[0] # 0: Double, 1: int32

if list == 4:
    tag = "double_nlevurb_numurbl_y_x"
    iVariable_list = Variable_urban_double_3D_nlev
    iVariable_type = Variable_type[0] # 0: Double, 1: int32
    
if list == 5:
    tag = "double_numrad_numurbl_y_x"
    iVariable_list = Variable_urban_double_3D_nrad
    iVariable_type = Variable_type[0] # 0: Double, 1: int32    
    
Points_in_land = "DataConversion_info/original_points_index.csv"
outputfile = 'surface_properities_1kmx1km_urban_'+tag+'_new.nc'

if Path(outputfile).exists():
    os.remove(outputfile)
    
# get the fine resolution data and the locations (lat, lon)
r_daymet = nc.Dataset('Daymet_FSDS.nc', 'r', format='NETCDF4')
x_coor = r_daymet.variables['x'][:]  # 1D x-axis
y_coor = r_daymet.variables['y'][:]  # 1D y-axis
FSDS = r_daymet.variables['FSDS'][0,:,:]

mask_d = np.where(~np.isnan(FSDS), 1, 0)
data = np.zeros((len(y_coor),len(x_coor)), dtype=iVariable_type)
f_data = np.ma.array(data, mask=mask_d)
grid_x, grid_y = np.meshgrid(x_coor,y_coor)
grid_y1 = grid_y[f_data.mask]
grid_x1 = grid_x[f_data.mask]
f_data1 = f_data[f_data.mask]

print("single layer grid is ready")

if save:
    # Open a new NetCDF file to write the data to. For format, you can choose from
    # 'NETCDF3_CLASSIC', 'NETCDF3_64BIT', 'NETCDF4_CLASSIC', and 'NETCDF4'
    w_nc_fid = nc.Dataset(outputfile, 'w', format='NETCDF4')
    w_nc_fid.title = 'The 1kmx1km surface propertties derived from a 0.5 degree global dataset'

    # create the dimension variable
    x_dim = w_nc_fid.createDimension('x_dim', len(x_coor))
    y_dim = w_nc_fid.createDimension('y_dim', len(y_coor))
    urb_dim = w_nc_fid.createDimension('numurbl', numurbl)
    nlurb_dim = w_nc_fid.createDimension('nlevurb', nlevurb)
    nrad_dim = w_nc_fid.createDimension('numrad', numrad)
    time_dim = w_nc_fid.createDimension('time_dim', None)


# read in the points within daymet land mask
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

print ('location of data points is ready')

# read in the source data
r_surf = nc.Dataset('surfdata.nc', 'r', format='NETCDF4')

for v in range(len(iVariable_list)):
    source = r_surf.variables[iVariable_list[v]][:]
    
    if (len(source.shape) == 2):
        layer = 1
        out_layer = 1
        all_data = np.zeros((len(y_coor),len(x_coor)), dtype=iVariable_type)

    if (len(source.shape) == 3):
        layer = source.shape[0]  #(3, 360, 720)
        out_layer = 1
        all_data = np.zeros((layer, len(y_coor),len(x_coor)), dtype=iVariable_type)

    if (len(source.shape) == 4):
        layer = source.shape[1]  #(5, 3, 360, 720)
        out_layer = source.shape[0]      
        all_data = np.zeros((out_layer, layer, len(y_coor),len(x_coor)), dtype=iVariable_type)

    for ol in range(out_layer):    
        for l in range(layer):  
            for i in range(land_points):
                # source is in [lat, lon] format
                if (len(source.shape) == 2):
                    o_data[i] = source[int(points_in_daymet_land[i][4]),int(points_in_daymet_land[i][5])]
                if (len(source.shape) == 3):                
                    o_data[i] = source[l, int(points_in_daymet_land[i][4]),int(points_in_daymet_land[i][5])]
                if (len(source.shape) == 4):  
                    o_data[i] = source[ol, l, int(points_in_daymet_land[i][4]),int(points_in_daymet_land[i][5])]
                    
            f_data1 = griddata(points, o_data, (grid_y1, grid_x1), method=iMethod)
            # put the masked data back to the data (with the daymet land mask)
            f_data = np.ma.array(data, mask=mask_d)
            f_data[f_data.mask]=f_data1
            
            if (len(source.shape) == 2):
                all_data = f_data
            if (len(source.shape) == 3):
                all_data[l,:,:] = f_data
            if (len(source.shape) == 4):
                all_data[ol, l,:,:] = f_data                
            print(str(l) + " layer is ready")
            
    if save:
            
        if list==1:
            w_nc_var = w_nc_fid.createVariable(iVariable_list[v], iVariable_type, 
                                   ('y_dim', 'x_dim'))       
        if (list==2 or list == 3):  
            w_nc_var = w_nc_fid.createVariable(iVariable_list[v], iVariable_type, 
                                   ('numurbl', 'y_dim', 'x_dim'))       
        if list==4:
            w_nc_var = w_nc_fid.createVariable(iVariable_list[v], iVariable_type, 
                                   ('nlevurb', 'numurbl', 'y_dim', 'x_dim'))   
        if list==5:
            w_nc_var = w_nc_fid.createVariable(iVariable_list[v], iVariable_type, 
                                   ('numrad', 'numurbl', 'y_dim', 'x_dim'))   
              
        w_nc_var.long_name = iVariable_list[v]    
        w_nc_fid.variables[iVariable_list[v]][:] = all_data
        print(" Variable: "+ iVariable_list[v] + " is done")

if save:
    w_nc_fid.close()  # close the new file

#plt.imshow(all_data[0,::5,::5])

