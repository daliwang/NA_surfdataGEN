## VegMapLandUnit rebuild plan (PFT, glacier, lake, urban, temperature)

Prereq
- `pft0_landtype19_nalcms_Snow_Ice_in_daymet.nc` has been renamed to `glacier_landtype19_nalcms_Snow_Ice_in_daymet.nc` so glacier is NOT treated as a PFT.
- Python environment activated.

### 1) Backup previous outputs

```bash
mv /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/combined_pft_count.nc \
   /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/combined_pft_count.bak.nc 2>/dev/null || true

mv /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/pft_total_count_percentage.nc \
   /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/pft_total_count_percentage.bak.nc 2>/dev/null || true
```

### 2) Rebuild PFT counts (glacier excluded)

```bash
cd /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs
python3 combine_pft_counts.py
```

Outputs `ELM_PFT_output/combined_pft_count.nc` assembled from all files matching `pft*.nc`.

### 3) Recompute PFT percentages of NATVEG

```bash
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/pft_total_count_percentage.py
```

Outputs `ELM_PFT_output/pft_total_count_percentage.nc`.

### 4) Rebuild totals/percentages for PFT + urban + lake + glacier

```bash
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/pft_urban_lake_glacier_percentage.py
```

Outputs combined counts/percentages including glacier `combined_pft_urban_lake_glacier_total_count.nc`.

### 5) Generate land_veg_urban_lake_glacier_percentage.nc

If not produced elsewhere, build from the combined counts:

```bash
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/make_land_veg_urban_lake_glacier_percentage.py \
  --in  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.nc \
  --out /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/land_veg_urban_lake_glacier_percentage.nc
```

### 6) Crop inputs to Surfdata grid (dx=98, dy=72)

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
  --land-file  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/pft_total_count_percentage.nc \
  --dx 98 --dy 72 \
  --out-cropped /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/pft_total_count_percentage.cropped_to_surfdata.nc

# Combined counts (align counts as well)
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/crop_align_merge.py \
  --surf-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc \
  --land-file  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.nc \
  --dx 98 --dy 72 \
  --out-cropped /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.cropped_to_surfdata.nc
```

### 7) Merge cropped land_veg into Surfdata

```bash
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/crop_align_merge.py \
  --surf-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc \
  --land-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/land_veg_urban_lake_glacier_percentage.cropped_to_surfdata.nc \
  --dx 0 --dy 0 \
  --out-cropped /tmp/noop.nc \
  --out-merged  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_glacier.nc
```

### 8) Add AvgTemp as AvgTempColdMonth (with orientation fix)

```bash
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/add_temp_to_surfdata.py \
  --surf-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_glacier.nc \
  --temp-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/mean_temperature_coldest_month.nc \
  --out-file  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_glacier_temp.nc
```

### 9) Optional: Fix lon/lat units (projected x/y should be meters)

```bash
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/fix_xy_units.py \
  --in  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_glacier_temp.nc \
  --out /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_glacier_temp.fixed_units.nc
```

### 10) Convert to final NetCDF (float32, dims x/y, compression 5)

```bash
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/convert_surfdata_float32.py \
  --in  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_glacier_temp.nc \
  --out /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/NA_surfdata_nalcms2daymet_pft_landunit_temp.nc \
  --level 5
```

### 11) Build a new surfdata-like file (maps + counts + PFT breakdown)

```bash
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/build_vegmap_surfdata_from_combined.py \
  --template /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc \
  --combined /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/NA_surfdata_nalcms2daymet_pft_landunit_temp.nc \
  --pft-breakdown /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/pft_total_count_percentage.cropped_to_surfdata.nc \
  --counts /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.cropped_to_surfdata.nc \
  --out /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.nc \
  --with-date-stamp --stamp-format c%y%m%d
```

Notes:
- Keeps `LONGXY`, `LATIXY`, `gridID`, `AREA`, `natpft` from the template.
- Writes `PCT_LAKE`, `PCT_GLACIER`, `PCT_URBAN(numurbl=3)`, `PCT_NATVEG`, `PCT_NAT_PFT(natpft,y,x)`.
- Carries counts: `pft_total_count`, `urban_count`, `lake_count`, `glacier_count`, `total_count`, and original per-PFT counts `pft0_count..pft16_count` (zeros if missing). Count variables include long_name/description.

### 12) Validate and plot (no coarsen)

```bash
python3 /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/validate_visualize_surfdata.py \
  --file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260122.nc \
  --vars PCT_NATVEG PCT_LAKE PCT_URBAN PCT_GLACIER AvgTempColdMonth \
  --validate --stats --plot --save \
  --outdir /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260122.nc \
  --coarsen 1
```

Notes
- Step 2 automatically excludes glacier because the collector only globs files starting with `pft`.
- `LATIXY/LONGXY` remain in degrees (geographic). `lat/lon` represent projected y/x and, starting with the updated crop/merge step, are written with units set to meters. Step 9 is only needed for legacy files created before this change or if units are incorrect.

