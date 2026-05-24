# Internal Validation Summary

## Key Metrics

| Category | Check | Value | Units | Notes |
|---|---:|---:|---|---|
| final product | source file | surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc |  | /Users/7xw/Documents/Work/papers/NALCMS_sn-article/DaymetVeg_LandUnit_DataProduct/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc |
| final product | valid land cells | 21128080 | cells |  |
| final product | full-land cells | 20820165 | cells | total_count >= 1089 |
| final product | partial-land cells | 307915 | cells | 0 < total_count < 1089 |
| final product | PFT closure cells checked | 20639331 | cells |  |
| final product | PFT closure failures | 10 | cells | absolute error > 0.001 |
| final product | maximum PFT closure error | 100 | percentage points |  |
| final product | mean PFT closure error | 4.90054e-05 | percentage points |  |
| final product | land-unit closure cells checked | 21128080 | cells |  |
| final product | land-unit closure failures | 0 | cells | absolute error > 0.001 |
| final product | maximum land-unit closure error | 7.62939e-06 | percentage points |  |
| final product | mean land-unit closure error | 6.33438e-08 | percentage points |  |
| intermediate counts | class-count closure | skipped |  |  |

## Climate Split Conservation

| landtype | pft_variables | lower_c | upper_c | source_nonzero_cells | residual_failures | residual_failure_percent_source_cells | max_abs_residual_pixels | mtco_min_c | mtco_mean_c | mtco_max_c |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pft1_count+pft2_count | -19 | -2 | 9097992 | 1740 | 0.0191251 | 1112 | -48.7647 | -20.6618 | 24.3402 |
| 8 | pft10_count+pft11_count | -15 | 5 | 8788306 | 1411 | 0.0160554 | 863 | -53.794 | -18.5986 | 23.8377 |
| 10 | pft12_count+pft13_count | -19 | -19 | 7694802 | 1081 | 0.0140484 | 400 | -54.5138 | -15.893 | 24.6245 |
| 5 | pft7_count+pft8_count | -15 | 5 | 4776579 | 337 | 0.00705526 | 568 | -44.0105 | -12.5343 | 23.4432 |
| 6 | pft7_count+pft8_count | -19 | 5 | 5380763 | 756 | 0.0140501 | 294 | -44.6195 | -17.0811 | 23.4245 |
