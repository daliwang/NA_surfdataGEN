## Split landtype3 into pft4/pft5 and rebuild surfdata

This README documents how to split `landtype3_nalcms_Tropical_evergreen_in_daymet.nc`
into `pft4` and `pft5` using a temperature threshold (default 18 C), then rebuild
the VegMapLandUnitTemp surfdata while keeping total vegetation percentage unchanged.

### Prerequisites

- Python environment activated with `netCDF4`, `numpy`, `xarray`, `matplotlib`.
- `pft4_landtype3_nalcms_Tropical_evergreen_in_daymet.nc` and
  `pft5_landtype3_nalcms_Tropical_evergreen_in_daymet.nc` are generated into a folder.

### 1) Split landtype3 into pft4 and pft5

```bash
cd /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs
python3 split_tropical_evergreen_18C.py --threshold-c 18 --plot
```

Outputs (default):
- `ELM_PFT_output_split_18C/pft4_landtype3_nalcms_Tropical_evergreen_in_daymet.nc`
- `ELM_PFT_output_split_18C/pft5_landtype3_nalcms_Tropical_evergreen_in_daymet.nc`
- PNG plots in the same folder

### 2) Replace the original pft4 file used for PFT aggregation

Copy the split outputs into the main `ELM_PFT_output` directory so they are picked
up by the PFT aggregation scripts.

```bash
cd /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs

# Backup original (no-split) pft4 if it exists
mv ELM_PFT_output/pft4_landtype3_nalcms_Tropical_evergreen_in_daymet.nc \
   ELM_PFT_output/nosplit_pft4_landtype3_nalcms_Tropical_evergreen_in_daymet.nc 2>/dev/null || true

# Copy split outputs
cp ELM_PFT_output_split_18C/pft4_landtype3_nalcms_Tropical_evergreen_in_daymet.nc ELM_PFT_output/
cp ELM_PFT_output_split_18C/pft5_landtype3_nalcms_Tropical_evergreen_in_daymet.nc ELM_PFT_output/
```

### 3) Rebuild PFT counts and percentages (NATVEG total unchanged)

```bash
cd /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output
python3 ../combine_pft_counts.py
python3 ../pft_total_count_percentage.py
python3 ../pft_urban_lake_glacier_percentage.py
```

Outputs:
- `ELM_PFT_output/combined_pft_count.nc`
- `ELM_PFT_output/pft_total_count_percentage.nc`
- `ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.nc`

### 4) Build land/veg/urban/lake/glacier percentage file

Working directory for this step:
`/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output`

```bash
cd /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/make_land_veg_urban_lake_glacier_percentage.py \
  --in  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.nc \
  --out /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/land_veg_urban_lake_glacier_percentage.nc
```

### 5) Crop/align to surfdata grid

```bash
# land/veg/urban/lake/glacier percentages
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/crop_align_merge.py \
  --surf-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc \
  --land-file  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/land_veg_urban_lake_glacier_percentage.nc \
  --dx 98 --dy 72 \
  --out-cropped /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/land_veg_urban_lake_glacier_percentage.cropped_to_surfdata.nc

# PFT breakdown (per-PFT percentages and counts)
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/crop_align_merge.py \
  --surf-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc \
  --land-file  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/ELM_PFT_output/pft_total_count_percentage.nc \
  --dx 98 --dy 72 \
  --out-cropped /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/pft_total_count_percentage.cropped_to_surfdata.nc

# Combined counts (align counts as well)
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/crop_align_merge.py \
  --surf-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc \
  --land-file  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.nc \
  --dx 98 --dy 72 \
  --out-cropped /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.cropped_to_surfdata.nc
```

### 6) Merge land/veg into surfdata and add temperature

```bash
# Merge updated land/veg/urban/lake/glacier percentages into surfdata
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/crop_align_merge.py \
  --surf-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc \
  --land-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/land_veg_urban_lake_glacier_percentage.cropped_to_surfdata.nc \
  --dx 0 --dy 0 \
  --out-cropped /tmp/noop.nc \
  --out-merged  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_glacier.nc

# Add AvgTempColdMonth
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/add_temp_to_surfdata.py \
  --surf-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_glacier.nc \
  --temp-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/mean_temperature_coldest_month.nc \
  --out-file  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_glacier_temp.nc
```

### 7) Convert to float32 and build VegMapLandUnitTemp surfdata

```bash
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/convert_surfdata_float32.py \
  --in  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_glacier_temp.nc \
  --out /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/NA_surfdata_nalcms2daymet_pft_landunit_temp.nc \
  --level 5

python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/build_vegmap_surfdata_from_combined.py \
  --template /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc \
  --combined /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/NA_surfdata_nalcms2daymet_pft_landunit_temp.nc \
  --pft-breakdown /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/pft_total_count_percentage.cropped_to_surfdata.nc \
  --counts /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.cropped_to_surfdata.nc \
  --out /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.nc \
  --with-date-stamp --stamp-format c%y%m%d
```

### Notes

- This workflow follows the steps in `dataProduct_DOI/README_VegMapLandUnit_Rebuild.md`.
- Total `PCT_NATVEG` remains unchanged; only the split between `pft4` and `pft5`
  is updated.
- If you need a fixed output filename, replace the `--out` path in step 7.


### Visulize and Verfiy the Results
  python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/validate_visualize_surfdata.py \
  --file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc \
  --vars PCT_NAT_PFT \
  --category-mode each \
  --category-dim natpft \
  --plot --save \
  --outdir /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/figures_c260128/surfdata_figs_VegMapLandUnit_PCT_NAT_PFT

  python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/validate_visualize_surfdata.py \
  --file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc \
  --vars PCT_NATVEG PCT_LAKE PCT_URBAN PCT_GLACIER AvgTempColdMonth \
  --validate --stats --plot --save \
  --outdir /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/figures_c260128/surfdata_figs_VegMapLandUnit \