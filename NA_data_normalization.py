import netCDF4 as nc
import numpy as nphw

source_file = 'NADaymet_surfdata.Daymet_NA.1km.1d.c240327.nc'
# open the 1D domain data
src = nc.Dataset(source_file, 'a', format='NETCDF4')

sand_pct= src['PCT_SAND'][...]
clay_pct= src['PCT_CLAY'][...]
nat_pft_pct=src['PCT_NAT_PFT'][...]

natveg_pct=src['PCT_NATVEG'][...]
natveg_pct[0:5]=natveg_pct[6:11]
natveg_pct[1916098]=natveg_pct[1916099]
natveg_pct[1919738]=natveg_pct[1919739]

crop_pct=src['PCT_CROP'][...]
crop_pct[0:5]=crop_pct[6:11]
crop_pct[1916098]=crop_pct[1916099]
crop_pct[1919738]=crop_pct[1919739]

wetland_pct=src['PCT_WETLAND'][...]
wetland_pct[0:5]=wetland_pct[6:11]
wetland_pct[1916098]=wetland_pct[1916099]
wetland_pct[1919738]=wetland_pct[1919739]

lake_pct=src['PCT_LAKE'][...]
lake_pct[0:5]=lake_pct[6:11]
lake_pct[1916098]=lake_pct[1916099]
lake_pct[1919738]=lake_pct[1919739]

glacier_pct=src['PCT_GLACIER'][...]
glacier_pct[0:5]=glacier_pct[6:11]
glacier_pct[1916098]=glacier_pct[1916099]
glacier_pct[1919738]=glacier_pct[1919739]

urban_pct=src['PCT_URBAN'][...]
urban_pct[0][0:5]=urban_pct[0][6:11]
urban_pct[1][0:5]=urban_pct[1][6:11]
urban_pct[2][0:5]=urban_pct[2][6:11]
urban_pct[0][1916098]=urban_pct[0][1916099]
urban_pct[1][1916098]=urban_pct[1][1916099]
urban_pct[2][1916098]=urban_pct[2][1916099]
urban_pct[0][1919738]=urban_pct[0][1919739]
urban_pct[1][1919738]=urban_pct[1][1919739]
urban_pct[2][1919738]=urban_pct[2][1919739]

gridcell=len(natveg_pct)
print(gridcell)

wt_lunit= natveg_pct+lake_pct+sum(urban_pct) + wetland_pct+glacier_pct+crop_pct

lake_pct_n=lake_pct/wt_lunit * 100
natveg_pct_n=natveg_pct/wt_lunit * 100
urban_pct_n=np.zeros((3,gridcell), dtype=np.float64)
urban_pct_n[0]=urban_pct[0]/wt_lunit * 100
urban_pct_n[1]=urban_pct[1]/wt_lunit * 100
urban_pct_n[2]=urban_pct[2]/wt_lunit * 100
wetland_pct_n= wetland_pct/wt_lunit * 100
glacier_pct_n=glacier_pct/wt_lunit * 100
crop_pct_n   =crop_pct/wt_lunit * 100

wt_lunit_n = natveg_pct_n+lake_pct_n+sum(urban_pct_n) + wetland_pct_n+glacier_pct_n+crop_pct_n

src['PCT_NATVEG'][...]=natveg_pct_n
src['PCT_CROP'][...]=crop_pct_n
src['PCT_WETLAND'][...]=wetland_pct_n
src['PCT_LAKE'][...]=lake_pct_n
src['PCT_GLACIER'][...]=glacier_pct_n
src['PCT_URBAN'][...]=urban_pct_n

src.close()

print((sum(wt_lunit)))

print((sum(wt_lunit_n)))