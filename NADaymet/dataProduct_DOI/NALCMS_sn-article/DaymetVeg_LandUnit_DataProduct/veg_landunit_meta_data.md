# README Metadata File

*This README file was updated on 2026-06-03 by Dali Wang*  

---

## GENERAL INFORMATION

1. **Title of Dataset:**  
    Gridded Vegetation and Land Unit Datasets over North America (1km x 1km) for E3SM Land Model
2. **Author Information**  
   **A. Principal Investigator Contact Information**  
   - Name: Dali Wang  
   - ORCID: 0000-0001-6806-5108  https://orcid.org/0000-0001-6806-5108
   - Institution:  Oak Ridge National Laboratory
   - Email:  wangd@ornl.gov

   **B. Associate or Co-investigator Contact Information**  
   - Name:  Rachael Youzhi Wang
   - ORCID:  
   - Institution:  The University of Tennessee, Knoxville
   - Email:  youzhi.wang@utk.edu

   - Name:  Peter Thornton
   - ORCID:  0000-0002-4759-5158  https://orcid.org/0000-0002-4759-5158
   - Institution:  Oak Ridge National Laboratory
   - Email:  thorntonpe@ornl.gov

   - Name:  Daniel Ricciuto
   - ORCID:  0000-0002-3668-3021  https://orcid.org/0000-0002-3668-3021
   - Institution:  Oak Ridge National Laboratory
   - Email:  ricciutodm@ornl.gov

   **C. Alternate Contact Information**  
   - Name:  
   - ORCID:  
   - Institution:  
   - Email:  

3. **Date of data collection:**  
   2026-06-03

4. **Geographic location of data collection:**  
   North America within Lambert Conformal Conic projection

5. **Information about funding sources that supported the collection of the data:**  
This work was supported by the U.S. Department of Energy, Office of Science, Office of Biological and Environmental Research, Earth and Environmental System Modeling program.
---

## SHARING/ACCESS INFORMATION

1. **Reuse restrictions placed on the data:**  

2. **Links to publications that cite or use the data:**  

3. **Links to other publicly accessible locations of the data:**  
   Current data record: `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260603.nc` — https://doi.org/10.13139/OLCF/3364821  
   Prior public release: `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c251230.nc` — https://doi.org/10.13139/OLCF/3005830

4. **Links/relationships to ancillary data sets:**  

5. **Was data derived from another source? If yes, list source(s):**  
   North American Land Change Monitoring System (NALCMS) land cover and Daymet Version 4 Revision 1.

6. **Recommended citation for this dataset:**  
   Wang, D., Wang, Y. R., Thornton, P., Ricciuto, D. Gridded vegetation and land unit datasets over North America for E3SM Land Model (`surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260603.nc`). Oak Ridge Leadership Computing Facility. https://doi.org/10.13139/OLCF/3364821 (2026).
   
   Prior version: Wang, D. Vegetation and land unit datasets over North America for E3SM Land Model (`surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c251230.nc`). Oak Ridge Leadership Computing Facility. https://doi.org/10.13139/OLCF/3005830 (2025).

---

## DATA & FILE OVERVIEW

1. **File List:**  
   surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260603.nc

2. **Relationship between files:**  
   `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260603.nc` is the current OLCF data record at https://doi.org/10.13139/OLCF/3364821 and supersedes `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c251230.nc` (https://doi.org/10.13139/OLCF/3005830). Relative to the prior release, this product adds: (1) **glacier handling**—NALCMS class 19 (Snow/Ice) maps to `PCT_GLACIER` rather than PFT0; (2) **climate-informed PFT splits**—Daymet mean temperature of the coldest month (MTCO) rules split selected NALCMS classes, including an **18 °C threshold** for tropical evergreen (class 3), with `AvgTempColdMonth` in the final NetCDF; (3) **inland open water**—extension of `na_mask` for open-water 1 km cells and lake land-unit assembly; (4) **Great Lakes mask completion**—shoreline and bounding-box cells around the five Great Lakes set to `na_mask=1`; (5) **full landtype re-count for open-water cells**—all NALCMS classes 1–19 aggregated from 30 m source for cells opened by the mask extension; (6) **diagnostic fields in the NetCDF**—`pft_percentage`, `urban_percentage`, `lake_percentage`, `glacier_percentage`, and `land_fraction` written alongside ELM `PCT_*` fields and pixel counts (`gridID`, `pft_total_count`, `urban_count`, `lake_count`, `glacier_count`, `total_count`).

3. **Additional related data collected that was not included in the current data package:**  

4. **Are there multiple versions of this dataset? If yes, what files were updated and why?**  
   Yes. `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c251230.nc` (2025-12-30) is the initial public release at https://doi.org/10.13139/OLCF/3005830. `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260603.nc` (2026-06-03) is the current data record at https://doi.org/10.13139/OLCF/3364821; it supersedes the prior file with glacier land units, MTCO-based PFT splits, inland open-water mask extension, Great Lakes mask completion, full class 1–19 re-count for newly opened mask cells, `AvgTempColdMonth`, and diagnostic count/percentage fields in the NetCDF.

---

## METHODOLOGICAL INFORMATION

1. **Description of methods used for collection/generation of data:**  
   The vegetation map was generated by the scripts in nalcms2daymet_script directory in the repository at `https://github.com/daliwang/NALCMS2Daymet_ELM`. 

2. **Methods for processing the data:**  
   The methods are described in `methods_nalcms_to_daymet.tex` and `methods_nadaymet.tex` in the NALCMS2Daymet_ELM repository at `https://github.com/daliwang/NALCMS2Daymet_ELM`. Those documents cover NALCMS reprojection and class counting (active-domain mask, inland open-water extension, and targeted re-count of newly opened cells), MTCO-based PFT assignment (including the 18 °C tropical-evergreen split and glacier land-unit handling), Great Lakes mask extension, and final surfdata assembly (`build_vegmap_surfdata_from_combined.py`).

---

## DATA-SPECIFIC INFORMATION FOR: surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260603.nc

1. **Number of variables:**  
   23 (coordinates `y`, `x`, index `natpft`, and 20 data fields listed below)

2. **Number of cases/rows:**  
   x = 7814 ; y = 8075 ;  
   natpft = 17 ; numurbl = 3 ;

3. **Variable List:**  
   (Names and dimensions match the NetCDF; float fields are `float32`, integer count fields are `int16`.)

```
double y(y) ;
double x(x) ;
int natpft(natpft) ;
float LONGXY(y, x) ;
float LATIXY(y, x) ;
short gridID(y, x) ;
float AREA(y, x) ;
float PCT_LAKE(y, x) ;
float PCT_GLACIER(y, x) ;
float PCT_NATVEG(y, x) ;
float PCT_URBAN(numurbl, y, x) ;
float PCT_NAT_PFT(natpft, y, x) ;
float AvgTempColdMonth(y, x) ;
short pft_total_count(y, x) ;
short urban_count(y, x) ;
short lake_count(y, x) ;
short glacier_count(y, x) ;
short total_count(y, x) ;
float pft_percentage(y, x) ;
float urban_percentage(y, x) ;
float lake_percentage(y, x) ;
float glacier_percentage(y, x) ;
float land_fraction(y, x) ;
```

   **ELM surfdata fractions (sum to 100% on land cells):** `PCT_LAKE`, `PCT_GLACIER`, `PCT_NATVEG`, `PCT_URBAN` (three urban density layers), `PCT_NAT_PFT` (natural vegetation PFTs 0–16).  

   **Pixel counts (30 m tallies per 1 km cell):** `pft_total_count`, `urban_count`, `lake_count`, `glacier_count`, `total_count`; `-1` indicates ocean or cells outside the active mask.  

   **Diagnostic percentages (fraction of active land-unit pixel total):** `pft_percentage`, `urban_percentage`, `lake_percentage`, `glacier_percentage`—used in pipeline QA; correspond to `PCT_NATVEG`, urban, lake, and glacier land units before surfdata normalization.  

   **`land_fraction`:** estimated fraction of the 1 km cell that is land (`100` if `total_count >= 1089`, else `total_count / 1156 × 100`). There is **no** variable named `lake_fraction`; use `land_fraction` and `PCT_LAKE` for lake coverage.

4. **Codes used for missing data:**  
   Ocean and inactive mask cells: `LONGXY` / `LATIXY` may be NaN; count variables use `-1`; some fields may use NetCDF fill value `-32767` where written from intermediate int16 layers.

5. **Specialized formats or other abbreviations used:**  
   PFT indices follow ELM `natpft` ordering (0–16). Urban layers follow `numurbl = 3`. Projection metadata for the Daymet grid is in companion files under `NADaymet/entire_domain/` (see processing repository).
