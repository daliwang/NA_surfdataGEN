# Sanity Check: surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260603.nc

**Date:** 2026-06-03 (post open-water recount fix)
**File:** `NADaymet/dataProduct_DOI/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260603.nc`

## Extended checks

- Land-unit closure failures (>0.01 pp): 0 / 21,356,113
-   max error: 0.000005 pp
- PFT closure failures (>0.01 pp): 10418 / 20,648,442 (max 100 pp)
- GL bbox land cells: 1,108,899
-   PCT_LAKE > 0: 607,353
-   PCT_LAKE == 100: 220,250
-   PCT_LAKE NaN on land: 0
- land_fraction range on land: 0.09 – 100.00
-   partial (<100%): 307,378
- Problem cell (j=4746,i=5822): PCT_LAKE=3.74, PCT_NATVEG=96.26, land_fraction=100.00, total_count=1122

## Internal validation

# Internal Validation Summary

## Key Metrics

| Category | Check | Value | Units | Notes |
|---|---:|---:|---|---|
| final product | source file | surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260603.nc |  | /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260603.nc |
| final product | valid land cells | 21356113 | cells |  |
| final product | full-land cells | 21048735 | cells | total_count >= 1089 |
| final product | partial-land cells | 307378 | cells | 0 < total_count < 1089 |
| final product | PFT closure cells checked | 20648442 | cells |  |
| final product | PFT closure failures | 10418 | cells | absolute error > 0.001 |
| final product | maximum PFT closure error | 100 | percentage points |  |
| final product | mean PFT closure error | 0.00338605 | percentage points |  |
| final product | land-unit closure cells checked | 21356113 | cells |  |
| final product | land-unit closure failures | 0 | cells | absolute error > 0.001 |
| final product | maximum land-unit closure error | 7.62939e-06 | percentage points |  |
| final product | mean land-unit closure error | 6.44383e-08 | percentage points |  |
| intermediate counts | class-count closure | skipped |  |  |

## Climate Split Conservation

| landtype | pft_variables | lower_c | upper_c | source_nonzero_cells | residual_failures | residual_failure_percent_source_cells | max_abs_residual_pixels | mtco_min_c | mtco_mean_c | mtco_max_c |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pft1_count+pft2_count | -19 | -2 | 9102793 | 4307 | 0.0473151 | 1112 | -48.7647 | -20.6629 | 24.3402 |
| 8 | pft10_count+pft11_count | -15 | 5 | 8789818 | 4143 | 0.0471341 | 1128 | -53.794 | -18.5991 | 23.8377 |
| 10 | pft12_count+pft13_count | -19 | -19 | 7697746 | 3705 | 0.048131 | 884 | -54.5138 | -15.8924 | 24.6245 |
| 5 | pft7_count+pft8_count | -15 | 5 | 4779846 | 914 | 0.019122 | 568 | -44.0105 | -12.5358 | 23.4432 |
| 6 | pft7_count+pft8_count | -19 | 5 | 5386532 | 1800 | 0.0334167 | 545 | -44.6195 | -17.0814 | 23.4245 |


## Figures

- `figures_c260603_surfdata_land_fraction_full_vs_gl_zoom.png`
- `figures_c260603_surfdata_pct_natveg_full_vs_gl_zoom.png`
- `figures_c260603_surfdata_pct_urban_full_vs_gl_zoom.png`
- `figures_c260603_surfdata_pct_lake_full_vs_gl_zoom.png`
- `figures_c260603_surfdata_pct_glacier_full_vs_gl_zoom.png`
- `figures_c260603_surfdata_pct_natpft00` … `natpft16` `_full_vs_gl_zoom.png`

## Commands

```bash
python3 run_sanity_and_figures_c260603.py
```