import os
import netCDF4 as nc
from scipy.interpolate import griddata
import numpy as np
from time import process_time
from pyproj import Transformer, CRS
import datetime
import argparse

def get_date_string():
    """Return current date as yymmdd string."""
    return datetime.datetime.now().strftime('%y%m%d')

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate 1D or 2D NA surfdata from 0.5x0.5 degree global surfdata."
    )
    parser.add_argument('input_surfdata', type=str, help='Input 0.5x0.5 degree global surfdata NetCDF filename')
    parser.add_argument('domain_type', type=str, choices=['1', '2'], help='1 for 1D, 2 for 2D domain')
    return parser.parse_args()

def main():
    args = parse_args()
    input_surfdata = args.input_surfdata
    domain_type = args.domain_type
    date_string = get_date_string()

    if domain_type == '1':
        output_file = f"surfdata.Daymet_NA.1km.1d.c{date_string}.nc"
    else:
        output_file = f"surfdata.Daymet_NA.1km.2d.c{date_string}.nc"

    # Only variables listed will be processed
    Variable_nearest = [
        'SLOPE', 'TOPO', 'PCT_GLACIER', 'PCT_LAKE', 'STD_ELEV',
        'PFTDATA_MASK', 'SOIL_COLOR', 'SOIL_ORDER', 'abm',
        'EF1_BTR', 'EF1_CRP', 'EF1_FDT', 'EF1_FET', 'EF1_GRS', 'EF1_SHR',
        'PCT_SAND', 'PCT_CLAY', 'ORGANIC', 'PCT_NAT_PFT',
        'URBAN_REGION_ID', 'NLEV_IMPROAD', 'T_BUILDING_MAX', 'T_BUILDING_MIN',
        'WIND_HGT_CANYON', 'WTLUNIT_ROOF', 'WTROAD_PERV', 'THICK_ROOF',
        'THICK_WALL', 'PCT_URBAN', 'HT_ROOF', 'EM_IMPROAD', 'EM_PERROAD',
        'EM_ROOF', 'EM_WALL', 'CANYON_HWR', 'TK_IMPROAD', 'TK_ROOF', 'TK_WALL',
        'CV_IMPROAD', 'CV_ROOF', 'CV_WALL', 'ALB_IMPROAD_DIF', 'ALB_IMPROAD_DIR',
        'ALB_PERROAD_DIF', 'ALB_PERROAD_DIR', 'ALB_ROOF_DIF', 'ALB_ROOF_DIR',
        'ALB_WALL_DIF', 'ALB_WALL_DIR'
    ]
    Variable_linear = [
        'FMAX', 'Ws', 'ZWT0', 'binfl', 'gdp', 'peatf', 'Ds', 'Dsmax', 'F0',
        'LAKEDEPTH', 'LANDFRAC_PFT', 'P3', 'PCT_NATVEG', 'PCT_WETLAND',
        'SECONDARY_P', 'OCCLUDED_P', 'LABILE_P', 'APATITE_P', 'PCT_CROP'
    ]

    # Exclude these variables from processing
    excluded_list = [
        'MONTHLY_LAI', 'MONTHLY_SAI', 'MONTHLY_HEIGHT_TOP', 'MONTHLY_HEIGHT_BOT'
    ]

    geoxy_proj_str = (
        "+proj=lcc +lon_0=-100 +lat_0=42.5 +lat_1=25 +lat_2=60 +x_0=0 +y_0=0 "
        "+R=6378137 +f=298.257223563 +units=m +no_defs"
    )
    geoxyProj = CRS.from_proj4(geoxy_proj_str)
    lonlatProj = CRS.from_epsg(4326)
    Txy2lonlat = Transformer.from_proj(geoxyProj, lonlatProj, always_xy=True)
    Tlonlat2xy = Transformer.from_proj(lonlatProj, geoxyProj, always_xy=True)

    # Open the source file
    with nc.Dataset(input_surfdata, 'r') as src:
        src_lat = src.variables['LATIXY'][...]
        src_lon = src.variables['LONGXY'][...]
        src_x, src_y = Tlonlat2xy.transform(src_lon, src_lat)
        src_lon[src_lon < 0.0] = 360 + src_lon[src_lon < 0.0]

        # Open the Daymet file
        with nc.Dataset('NA_TBOT.nc', 'r', format='NETCDF3_64BIT_DATA') as r_daymet:
            x_dim = r_daymet['x']
            y_dim = r_daymet['y']
            TBOT = r_daymet.variables['TBOT'][0, :, :]

            grid_ids = np.linspace(0, len(x_dim) * len(y_dim) - 1, len(x_dim) * len(y_dim), dtype=int)
            grid_ids = grid_ids.reshape(TBOT.shape)
            grid_xids = np.indices(grid_ids.shape)[1]
            grid_yids = np.indices(grid_ids.shape)[0]

            bool_mask = ~np.isnan(TBOT)
            grid_x, grid_y = np.meshgrid(x_dim, y_dim)
            lon, lat = Txy2lonlat.transform(grid_x, grid_y)

            grid_y1 = np.copy(grid_y[bool_mask])
            grid_x1 = np.copy(grid_x[bool_mask])
            gridcells = len(grid_x1)
            grid_lon, grid_lat = Txy2lonlat.transform(grid_x1, grid_y1)

            idxy = np.nonzero(
                (src_x <= (np.amax(grid_x) + 500)) & (src_x >= (np.amin(grid_x) - 500)) &
                (src_y <= (np.amax(grid_y) + 500)) & (src_y >= (np.amin(grid_y) - 500))
            )

            points_in_daymet_land = {
                0: src_x[idxy],
                1: src_y[idxy],
                2: src_lat[idxy],
                3: src_lon[idxy],
                4: idxy[0],
                5: idxy[1]
            }
            land_points = len(points_in_daymet_land[0])
            points = np.zeros((land_points, 2), dtype='double')
            points[:, 0] = src_y[idxy]
            points[:, 1] = src_x[idxy]

            if os.path.isfile(output_file):
                os.remove(output_file)

            with nc.Dataset(output_file, 'w') as dst:
                # Copy dimensions
                for name, dimension in src.dimensions.items():
                    dst.createDimension(name, (len(dimension) if not dimension.isunlimited() else None))

                # Copy global attributes and add input filename
                dst.setncatts(src.__dict__)
                dst.setncattr('input_surfdata_filename', os.path.basename(input_surfdata))

                # Create new dimensions for TES domain
                dst.createDimension('lon', x_dim.size)
                dst.createDimension('lat', y_dim.size)

                dst_var = dst.createVariable('lon', np.float64, ('lon',))
                dst_var.units = "degree"
                dst_var.long_name = "x coordinate of projection"
                dst_var.standard_name = "x_project_coordinate"
                dst['lon'][...] = np.copy(x_dim)
                dst_var = dst.createVariable('lat', np.float64, ('lat',))
                dst_var.units = "degree"
                dst_var.long_name = "y coordinate of projection"
                dst_var.standard_name = "projection_y_coordinate"
                dst['lat'][...] = np.copy(y_dim)

                if domain_type == '1':
                    dst_var = dst.createVariable('lon2D', np.float64, ('lat', 'lon'))
                    dst_var.units = "degrees_east"
                    dst_var.long_name = "longitude coordinate"
                    dst_var.standard_name = "longitude"
                    dst['lon2D'][...] = np.copy(lon)
                    dst_var = dst.createVariable('lat2D', np.float64, ('lat', 'lon'))
                    dst_var.units = "degrees_north"
                    dst_var.long_name = "latitude coordinate"
                    dst_var.standard_name = "latitude"
                    dst['lat2D'][...] = np.copy(lat)

                    dst.createDimension('gridcell', gridcells)
                    dst_var = dst.createVariable('gridID', np.int32, ('gridcell',))
                    dst_var.long_name = 'gridId in the NA domain'
                    dst_var.decription = "start from #0 at the upper left corner of the domain, covering all land and ocean gridcells"
                    dst['gridID'][...] = np.copy(grid_ids[bool_mask])

                    dst_var = dst.createVariable('gridXID', np.int32, ('gridcell',))
                    dst_var.long_name = 'gridId x in the NA domain'
                    dst_var.decription = "start from #0 at the upper left corner and from west to east of the domain, with gridID=gridXID+gridYID*x_dim"
                    dst.variables['gridXID'][...] = np.copy(grid_xids[bool_mask])

                    dst_var = dst.createVariable('gridYID', np.int32, ('gridcell',))
                    dst_var.long_name = 'gridId y in the NA domain'
                    dst_var.decription = "start from #0 at the upper left corner and from north to south of the domain, with gridID=gridXID+gridYID*y_dim"
                    dst.variables['gridYID'][...] = np.copy(grid_yids[bool_mask])
                else:
                    dst_var = dst.createVariable('gridID', np.int32, ('lat', 'lon'))
                    dst_var.long_name = 'gridId in the NA domain'
                    dst_var.decription = "start from #0 at the upper left corner of the domain, covering all land and ocean gridcells"
                    dst.variables['gridID'][...] = np.copy(grid_ids)

                    dst_var = dst.createVariable('gridXID', np.int32, ('lat', 'lon'))
                    dst_var.long_name = 'gridId x in the NA domain'
                    dst_var.decription = "start from #0 at the upper left corner and from west to east of the domain, with gridID=gridXID+gridYID*x_dim"
                    dst.variables['gridXID'][...] = np.copy(grid_xids)

                    dst_var = dst.createVariable('gridYID', np.int32, ('lat', 'lon'))
                    dst_var.long_name = 'gridId y in the NA domain'
                    dst_var.decription = "start from #0 at the upper left corner and from north to south of the domain, with gridID=gridXID+gridYID*y_dim"
                    dst.variables['gridYID'][...] = np.copy(grid_yids)

                count = 0
                for name, variable in src.variables.items():
                    # Skip excluded variables
                    if name in excluded_list:
                        continue
                    start = process_time()
                    print(f"Checking on variable: {name} dimensions: {variable.dimensions}")
                    if variable.dimensions[-2:] == ('lsmlat', 'lsmlon'):
                        iMethod = 'linear' if name in Variable_linear else 'nearest'
                        print(f"Working on variable: {name} dimensions: {variable.dimensions}")
                        fill_value = -9999 if variable.datatype == np.int32 else np.nan
                        if domain_type == '1':
                            x = dst.createVariable(name, variable.datatype, variable.dimensions[:-2] + ('gridcell',), fill_value=fill_value, zlib=True, complevel=5)
                        else:
                            x = dst.createVariable(name, variable.datatype, variable.dimensions[:-2] + ('lat', 'lon'), fill_value=fill_value, zlib=True, complevel=5)
                        dst[name].setncatts(src[name].__dict__)
                        f_data1 = np.zeros(gridcells, dtype=variable.datatype)
                        o_data = np.zeros(land_points, dtype=variable.datatype)
                        if len(variable.dimensions) == 2:
                            source = src[name][:]
                            o_data = source[points_in_daymet_land[4][:], points_in_daymet_land[5][:]]
                            f_data1 = griddata(points, o_data, (grid_y1, grid_x1), method=iMethod)
                            if name == 'AREA':
                                f_data1[...] = 1.0
                            if name == 'LONGXY':
                                f_data1[...] = grid_lon
                            if name == 'LATIXY':
                                f_data1[...] = grid_lat
                            if domain_type == '1':
                                dst[name][...] = np.copy(f_data1)
                            else:
                                f_data = np.ma.array(np.empty((len(y_dim), len(x_dim)), dtype=variable.datatype), mask=bool_mask, fill_value=fill_value)
                                f_data = np.where(f_data.mask, f_data, fill_value)
                                f_data[bool_mask] = f_data1
                                dst[name][...] = np.copy(f_data)
                            count += 1
                        elif len(variable.dimensions) == 3:
                            for index in range(variable.shape[0]):
                                source = src[name][index, :, :]
                                o_data = source[points_in_daymet_land[4][:], points_in_daymet_land[5][:]]
                                f_data1 = griddata(points, o_data, (grid_y1, grid_x1), method=iMethod)
                                if domain_type == '1':
                                    dst[name][index, ...] = np.copy(f_data1)
                                else:
                                    f_data = np.ma.array(np.empty((len(y_dim), len(x_dim)), dtype=variable.datatype), mask=bool_mask, fill_value=fill_value)
                                    f_data = np.where(f_data.mask, f_data, fill_value)
                                    f_data[bool_mask] = f_data1
                                    dst[name][index, ...] = np.copy(f_data)
                            count += variable.shape[0]
                        elif len(variable.dimensions) == 4:
                            for index1 in range(variable.shape[0]):
                                for index2 in range(variable.shape[1]):
                                    source = src[name][index1, index2, :, :]
                                    o_data = source[points_in_daymet_land[4][:], points_in_daymet_land[5][:]]
                                    f_data1 = griddata(points, o_data, (grid_y1, grid_x1), method=iMethod)
                                    if domain_type == '1':
                                        dst[name][index1, index2, ...] = np.copy(f_data1)
                                    else:
                                        f_data = np.ma.array(np.empty((len(y_dim), len(x_dim)), dtype=variable.datatype), mask=bool_mask, fill_value=fill_value)
                                        f_data = np.where(f_data.mask, f_data, fill_value)
                                        f_data[bool_mask] = f_data1
                                        dst[name][index1, index2, ...] = np.copy(f_data)
                            count += variable.shape[1]
                        end = process_time()
                        print(f"Generating variable: {name} takes {end - start}")
                    else:
                        xerr = dst.createVariable(name, variable.datatype, variable.dimensions, zlib=True, complevel=5)
                        dst[name].setncatts(src[name].__dict__)
                        dst[name][...] = src[name][...]
                        end = process_time()
                        print(f"Copying variable: {name} takes {end - start}")
                    if count > 50:
                        dst.sync()  # flush to disk
                        count = 0
                    print(count)

if __name__ == '__main__':
    main()