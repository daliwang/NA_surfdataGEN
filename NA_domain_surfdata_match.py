import netCDF4 as nc

# Open the source file in read mode
src_file = nc.Dataset('NADaymet_domain.lnd.Daymet_NA.1km.1d.c240521.nc', 'r')

# Read the data from the variables xc and yc
xc_data = src_file.variables['xc'][:]
yc_data = src_file.variables['yc'][:]

# Close the source file
src_file.close()

# Open the target file in append mode
tgt_file = nc.Dataset('NADaymet_surfdata.Daymet_NA.1km.1d.c240327.nc', 'a')

# Replace the values of LONGXY and LATIXY with the data read from the source file
tgt_file.variables['LONGXY'][:] = xc_data
tgt_file.variables['LATIXY'][:] = yc_data

# Close the target file
tgt_file.close()
