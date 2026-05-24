# Internal Validation Summary

## Key Metrics

| Category | Check | Value | Units | Notes |
|---|---:|---:|---|---|
| final product | source file | surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc |  | /Users/7xw/Documents/Work/papers/NALCMS_sn-article/DaymetVeg_LandUnit_DataProduct/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc |
| final product | valid land cells | 21345437 | cells |  |
| final product | full-land cells | 20821077 | cells | total_count >= 1089 |
| final product | partial-land cells | 524360 | cells | 0 < total_count < 1089 |
| final product | PFT closure cells checked | 20637628 | cells |  |
| final product | PFT closure failures | 10 | cells | absolute error > 0.001 |
| final product | maximum PFT closure error | 100 | percentage points |  |
| final product | mean PFT closure error | 4.90093e-05 | percentage points |  |
| final product | land-unit closure cells checked | 21345437 | cells |  |
| final product | land-unit closure failures | 0 | cells | absolute error > 0.001 |
| final product | maximum land-unit closure error | 7.62939e-06 | percentage points |  |
| final product | mean land-unit closure error | 6.32421e-08 | percentage points |  |
| intermediate land units | valid land cells | 21128080 | cells |  |
| intermediate land units | full-land cells | 20820165 | cells | total_count >= 1089 |
| intermediate land units | partial-land cells | 307915 | cells | 0 < total_count < 1089 |
| intermediate land units | land-unit closure cells checked | 21128080 | cells |  |
| intermediate land units | land-unit closure failures | 0 | cells | absolute error > 0.001 |
| intermediate land units | maximum land-unit closure error | 7.62939e-06 | percentage points |  |
| intermediate land units | mean land-unit closure error | 6.502e-08 | percentage points |  |
| intermediate counts | class-count closure cells checked | 21257202 | cells |  |
| intermediate counts | class-count closure failures | 3665 | cells |  |
| intermediate counts | maximum class-count residual | 1122 | 30 m pixels |  |
| intermediate counts | sum absolute class-count residual | 195430 | 30 m pixels |  |
| intermediate land units | land_fraction min | 0.0865052 | percent |  |
| intermediate land units | land_fraction max | 100 | percent |  |
| intermediate land units | land_fraction mean | 99.238 | percent |  |

## Climate Split Conservation

| landtype | pft_variables | lower_c | upper_c | source_nonzero_cells | residual_failures | residual_failure_percent_source_cells | max_abs_residual_pixels | mtco_min_c | mtco_mean_c | mtco_max_c |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pft1_count+pft2_count | -19 | -2 | 9097992 | 1740 | 0.0191251 | 1112 | -48.7647 | -20.6618 | 24.3402 |
| 8 | pft10_count+pft11_count | -15 | 5 | 8788306 | 1411 | 0.0160554 | 863 | -53.794 | -18.5986 | 23.8377 |
| 10 | pft12_count+pft13_count | -19 | -19 | 7694802 | 1081 | 0.0140484 | 400 | -54.5138 | -15.893 | 24.6245 |
| 5 | pft7_count+pft8_count | -15 | 5 | 4776579 | 337 | 0.00705526 | 568 | -44.0105 | -12.5343 | 23.4432 |
| 6 | pft7_count+pft8_count | -19 | 5 | 5380763 | 756 | 0.0140501 | 294 | -44.6195 | -17.0811 | 23.4245 |
