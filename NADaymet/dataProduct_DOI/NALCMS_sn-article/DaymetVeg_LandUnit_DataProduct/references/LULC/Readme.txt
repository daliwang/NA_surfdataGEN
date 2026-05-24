Global 1km Land Surface Parameters for Kilometer Scale Earth System Modeling

Version: 1.0
Data format: NetCDF.
Institution: Atmospheric Sciences and Global Change Division, Pacific Northwest National Laboratory
Contacts: Lingcheng Li (lingcheng.li@pnnl.gov; lingchengliwhu@gmail.com), Gautam Bisht (gautam.bisht@pnnl.gov)

Description: This dataset provides land surface parameters specifically designed for global kilometer scale earth system modeling.
Spatial resolution: 1 km, corresponding to 1/120 degree.
Temporal resolution: includes yearly (2001-2020), monthly (2001-2020), and static data for different parameters.
Reference: [To be added]

It includes four categories of parameters:
1. LULC: land use and land cover parameters
2. VEGE: vegetation paramertes
3. SOIL: soil parameters
4. TOPO: topography parameters

File names:
    -temporally static parameters: XXXX_1k_c230606.nc
        XXXX is the variable short names;
        c230606: the generation date, 2023 June 6;
    -monthly or yearly parameters: XXXX_YYYY_1k_c230606.nc
        XXXX is the variable short names
        YYYY is the year, from 2001 to 2020
        c230606: the generation date, 2023 June 6;

Specific parameters:
1. LULC, yearly. 
    -lake percent. Percent of grid cell that is covered by lake (including river)
        file name: PCT_LAKE_YYYY_1k_c230606.nc
        variables: PCT_GLACIER(lat, lon)
        valid values: 0 or 100
        unit: %
    
    -glacier percent. Percent of grid cell that is covered by land ice (either glaciers, ice caps, ice sheet, or ice shelves)
        file name: PCT_GLACIER_YYYY_1k_c230606.nc
        variables: PCT_GLACIER(lat, lon)
        valid values: 0 or 100
        unit: %

    -wetland percent. It acts as the mask for ocean(i.e., 100) or land(i.e., 0)
        file name: PCT_WETLAND_YYYY_1k_c230606.nc
        variables: PCT_WETLAND(lat, lon)
        valid values: 0 or 100
        unit: %

    -urban percent. Percent of grid cell that is covered by urban, include three urban density classes: tall building district (TBD), high density (HD), and medium density (MD)
        file name: PCT_URBAN_YYYY_1k_c230606.nc
        variables:PCT_URBAN(density, lat, lon). 
        valid values: 0 or 100
        unit: %
    
    -vegetated land percent (inlcuidng bare soil). Percent of grid cell that is covered by vegetation types, i.e., 17 plant functional types (PFTs, including bare soil)
     ! should use with the variable of PCT_NAT_PFT_INDEX for the specific PFTs
        file name: PCT_NATVEG_YYYY_1k_c230606.nc
        variables: PCT_NATVEG(lat, lon).
        valid values: 0 or 100
        unit: %

    -vegetated land index. Each grid cell is 100% covered by a specific plant functional types
     ! should use with the variable of PCT_NATVEG, the specific PFT for the vegetated land grid. 
        file name: PCT_NAT_PFT_INDEX_YYYY_1k_c230606.nc
        variables:PCT_NAT_PFT_INDEX(lat, lon)
        valid values: 0-16
        pft_category: 0 bare soil/ 1 Needleleaf evergreen tree, temperate/ 2 Needleleaf evergreen tree, boreal/ 3 Needleleaf deciduous tree/ 4 Broadleaf evergreen tree, tropical/ 5 Broadleaf evergreen tree, temperate/ 6 Broadleaf deciduous tree, tropical/7 Broadleaf deciduous tree, temperate/ 8 Broadleaf deciduous tree, boreal/ 9 Broadleaf evergreen shrub, temperate/10 Broadleaf deciduous shrub, temperate/ 11 Broadleaf deciduous shrub, boreal/ 12 C3 grass, arctic/13 C3 grass/ 14 C4 grass/ 15 Crop / 16 irrigated cropland
        unit: dimensionless

2. VEGE, monthly or static
    -leaf area index, monthly. 
        file name: LAI_YYYY_1k_c230606.nc
        variables: LAI(time, lat, lon)
        unit: m2 m-2
    -stem area index, monthly.
        file name: SAI_YYYY_1k_c230606.nc
        variables: SAI(time, lat, lon)
        unit: m2 m-2

    -vegetation canopy top height, temporally static. 
        file name: CANOPY_HEIGHT_BOT_1k_c230606.nc
        variables: CANOPY_HEIGHT_BOT(lat, lon) 
        unit: m
    
    -vegetation canopy bottom height, temporally static.
        file name: CANOPY_HEIGHT_BOT_1k_c230606.nc
        variables: CANOPY_HEIGHT_BOT(lat, lon)
        unit: m


3. SOIL, temporally static
   Soil parameters are prepared for two types of soil layers:
   1) 10 layers for use with the E3SM Land Model
      10 soil layer bottom depth (m), 0.0175, 0.0451, 0.0906, 0.1655, 0.2891, 0.4929, 0.8289, 1.3828, 2.2961, 3.8019
   2) 6 layers for general users, which align with the soil layers of the source data SOILGRID v2
      6 soil layer bottom depth (m), 0.05, 0.15, 0.3, 0.6, 1.0, 2.0
    
    -percent clay, 10 layers
        file name: PCT_CLAY_10layer_1k_c230606
        variables: PCT_CLAY(layer,lat, lon) 
        unit: %
        
    -percent sand, 10 layers
        file name: PCT_SAND_10layer_1k_c230606
        variables: PCT_SAND(layer,lat, lon) 
        unit: %
    
    -organic soil density, 10 layers
        file name: ORGANIC_10layer_1k_c230606
        variables: ORGANIC(layer,lat, lon) 
        unit: kg/m3 (assumed carbon content 0.58 gC per gOM)
    
    -percent clay, 6 layers 
        file name: PCT_CLAY_6layer_1k_c230606
        variables: PCT_CLAY(layer,lat, lon) 
        unit: %

    -percent sand, 6 layers
        file name: PCT_SAND_6layer_1k_c230606
        variables: PCT_SAND(layer,lat, lon) 
        unit: %    
    
    -organic soil density, 6 layers 
        file name: ORGANIC_6layer_1k_c230606
        variables:ORGANIC(layer,lat, lon) 
        unit: kg/m3 (assumed carbon content 0.58 gC per gOM)


4. TOPO, temporally static
    -elevation
        file name: ELEVATION_1k_c230606.nc
        variables: ELEVATION(lat, lon)
        unit: m
    
    -slope
        file name: SLOPE_1k_c230606.nc
        variables: SLOPE(lat, lon)
        unit: degree

    -aspect
        file name: ASPECT_1k_c230606.nc
        variables: ASPECT(lat, lon)
        unit: degree

    -standard deviation of elevation
        file name: STDEV_ELEV_1k_c230606.nc
        variables: STDEV_ELEV(lat, lon)
        unit: m

    -sky view factor
        file name: SKY_VIEW_FACTOR_1k_c230606.nc
        variables: SKY_VIEW_FACTOR(lat, lon)
        unit: dimensionless
    
    -terrain configuration factor
        file name: TERRAIN_CONFIG_1k_c230606.nc
        variables: TERRAIN_CONFIG(lat, lon)
        unit: dimensionless
