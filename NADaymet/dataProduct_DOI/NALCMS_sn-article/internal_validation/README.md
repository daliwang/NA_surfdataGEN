# Internal validation scripts

This folder contains scripts for quantitative internal validation of the NALCMS-to-Daymet ELM land-surface-property dataset.

## Script

`compute_internal_validation.py` reads:

- the final surfdata NetCDF (default: Great Lakes--corrected `c260128.great_lakes_fix.nc` in the paper repo)
- intermediate files under `/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet`

and writes:

- `results/summary_metrics.csv`
- `results/climate_split_conservation.csv`
- `results/internal_validation_summary.md`

## Checks

The current script computes:

- Final product land-unit closure:
  `PCT_NATVEG + PCT_LAKE + PCT_GLACIER + sum(PCT_URBAN) = 100`
- Final product PFT closure:
  `sum(PCT_NAT_PFT) = 100` where natural vegetation exists
- Land-fraction coverage statistics in the final product
- Intermediate class-count closure:
  `sum(NALCMS class counts 1-19) = total_count`
- Climate-split conservation:
  paired PFT counts sum back to the original NALCMS class count
- MTCO summary statistics over cells affected by climate-split rules

## Run

```bash
python3 internal_validation/compute_internal_validation.py
```

Validate the uncorrected base file instead:

```bash
python3 internal_validation/compute_internal_validation.py \
  --final-nc DaymetVeg_LandUnit_DataProduct/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc
```

To skip the class-count closure pass, which reads 19 large GeoTIFFs:

```bash
python3 internal_validation/compute_internal_validation.py --skip-class-count-closure
```
