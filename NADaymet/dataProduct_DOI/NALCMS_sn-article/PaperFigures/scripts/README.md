# Paper figure scripts

Scripts to regenerate MTCO figures used in `scientific_data_descriptor.tex`.

## Requirements

```bash
pip install xarray netCDF4 matplotlib numpy
```

## Input data

Default input:

```
/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/mean_temperature_coldest_month.nc
```

Variable: `AvgTemp` (mean temperature of coldest month, 1980–2014, Daymet grid).

Override with `--mtco-file` if the NetCDF is stored elsewhere.

## Generate all figures

From this directory:

```bash
python3 generate_mtco_plots.py
```

Outputs are written to `../` (`PaperFigures/`):

| File | Description |
|------|-------------|
| `MTCO_rule1_ranges.png` | Classified map: ≤ −19, −19 to −2, > −2 °C |
| `MTCO_rule2_ranges.png` | Classified map: ≤ −15, −15 to 5, 5 to 18, > 18 °C |
| `MTCO_rule1_thresholds.png` | Contour lines at −19 and −2 °C |
| `MTCO_rule2_thresholds.png` | Contour lines at −15, 5, and 18 °C |

## Options

```bash
# Classified range maps only
python3 generate_mtco_plots.py --plot-type ranges

# Contour threshold maps only
python3 generate_mtco_plots.py --plot-type thresholds

# Custom input and output
python3 generate_mtco_plots.py \
  --mtco-file /path/to/mean_temperature_coldest_month.nc \
  --outdir /path/to/PaperFigures \
  --dpi 220
```

## Related upstream script

Contour plotting for surfdata NetCDF files (variable `AvgTempColdMonth`) lives in the data-product repository:

```
NA_surfdataGEN/NADaymet/dataProduct_DOI/plot_avgtemp_contours.py
```

That script was used during early figure exploration; `generate_mtco_plots.py` in this folder is the reproducible source for the paper figures.

## PFT example panel (`generate_pft_panel.py`)

```bash
python3 generate_pft_panel.py
```

Default input: `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc`

Output: `../pft_1_2_7_8_panel.png` — 2×2 panel of PFT 1, 2, 7, and 8 with Daymet projected x/y coordinates (meters).

## Land-unit RGB map (`generate_landtype_rgb.py`)

```bash
python3 generate_landtype_rgb.py
```

Default input: `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc`

Output: `../landtype_rgb_map.png` — RGB map with green = `PCT_NATVEG`, red = urban, blue = `PCT_LAKE`. Glacier is alpha-blended toward dark gray by `PCT_GLACIER`; ocean remains white and is omitted from the legend. NaN glacier values are treated as zero so lake-only cells (e.g. Great Lakes after the open-water correction) are not masked as ocean.

Default input: `surfdata...c260128.great_lakes_fix.nc` (includes Great Lakes lake correction with 15 km polygon buffer).

**Pipeline note (2026-05-22):** An upstream fix extends `na_mask.tif` to include inland open water and patches class-18 counts. See `../README_NA_Mask_Open_Water_Fix.md` and `../Great_Lakes_Open_Water_Report.md`. After surfdata is rebuilt from the updated GeoTIFFs, regenerate this figure from the new base product instead of (or in addition to) `great_lakes_fix.nc`.

## Reprojection map (`generate_reprojection_figure.py`)

High-resolution Figure 3 from the reprojected 30 m NALCMS GeoTIFF:

```bash
python3 generate_reprojection_figure.py
```

Default input: `NA_surfdataGEN/NADaymet/entire_domain/nalcms2daymet_hcompressed.tif` (produced by the [NALCMS2Daymet_ELM](https://github.com/daliwang/NALCMS2Daymet_ELM) workflow; not stored in that git repo).

Output: `../../E3SM_1km_data_preparation/reprojection.png`

Options: `--max-width 4800`, `--boundary-width 5`, `--input-file`, `--output-file`

## Li et al. (2020) LULC comparison panels (`generate_li_lulc_comparison.py`)

Three-panel figures for lake, natural vegetation, glacier, and urban (NALCMS | Li et al. 2020 | difference):

```bash
python3 generate_li_lulc_comparison.py
```

Requires Li et al. 2020 LULC NetCDF files in `DaymetVeg_LandUnit_DataProduct/references/LULC/` (see `Readme.txt`).

Outputs under `PaperFigures/comparison/li_lulc_2020/`:

| File | Description |
|------|-------------|
| `pct_lake_lulc2020_vs_nalcms_panel.png` | Lake fraction comparison |
| `pct_natveg_lulc2020_vs_nalcms_panel.png` | Natural vegetation comparison |
| `pct_glacier_lulc2020_vs_nalcms_panel.png` | Glacier fraction comparison |
| `pct_urban_lulc2020_vs_nalcms_panel.png` | Total urban fraction comparison |

## E3SM historical land-use comparison panels (`generate_e3sm_landuse_comparison.py`)

Three-panel figures for lake, natural vegetation, glacier, and urban (NALCMS | E3SM 2015 | difference):

```bash
python3 generate_e3sm_landuse_comparison.py
```

Default E3SM input: `DaymetVeg_LandUnit_DataProduct/comparison/landuse.PCT_subset_last.nc` (2015 time slice).

Outputs under `PaperFigures/comparison/e3sm_landuse_2015/`:

| File | Description |
|------|-------------|
| `pct_lake_e3sm2015_vs_nalcms_panel.png` | Lake fraction comparison |
| `pct_natveg_e3sm2015_vs_nalcms_panel.png` | Natural vegetation comparison |
| `pct_glacier_e3sm2015_vs_nalcms_panel.png` | Glacier fraction comparison |
| `pct_urban_e3sm2015_vs_nalcms_panel.png` | Total urban fraction comparison |
