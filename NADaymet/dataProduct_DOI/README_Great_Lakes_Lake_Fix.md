# Great Lakes lake-landunit correction

> **2026-05-22 upstream fix:** `na_mask.tif` has been extended to include inland open water (class 18). See **`README_NA_Mask_Open_Water_Fix.md`** for the full changelog, verification tables, and pipeline rebuild steps. The post-processing script below remains valid for the current surfdata release until rebuild completes.

## Root cause

The 30 m NALCMS source (`NADaymet/entire_domain/nalcms2daymet_hcompressed.tif`) maps **Great Lakes open water as class 18 (Water)**. Lake fractions are missing in 1 km surfdata because of pipeline masking and count assembly:

1. **`na_mask.tif`** marks many open-lake 1 km cells as `mask=0`. `class_count_na_para.py` only counts 30 m pixels where `na_mask==1`, so `landtype18_count_in_namask.tif` stays `-1`.
2. **`pft_total_count_percentage.py`** sums PFT layers using `-1` sentinels, yielding negative totals (e.g. `-22`) on water-only cells inside the mask.
3. **`pft_urban_lake_glacier_percentage.py`** treats non-positive totals as non-land; **`crop_align_merge.py`** maps the result into surfdata with int16 fill (`-32767`).

Verified at lake centres:

| Location | 30 m source class | `na_mask` | `landtype18_count` |
|----------|-------------------|-----------|---------------------|
| Lake Michigan centre | 18 | 0 | -1 |
| Lake Superior centre | 18 | 0 | -1 |

Run **`diagnose_great_lakes_pipeline_gap.py`** for full Great Lakes bbox statistics.

See **`Great_Lakes_Open_Water_Report.md`** for the full diagnostic write-up.

## Upstream fix (applied 2026-05-22)

See **`README_NA_Mask_Open_Water_Fix.md`** for full documentation.

| Item | Detail |
|------|--------|
| Script | `extend_na_mask_open_water.py` |
| Mask change | +228,169 cells (`mask=0` → `1`) where 30 m centre = class 18 |
| Backups | `entire_domain/na_mask.tif.bak`, `NADaymet/na_mask.tif.bak` |
| Class-18 counts | `landtype18_count_in_namask.tif` patched for all new cells |
| PFT totals | `ELM_PFTs/pft_total_count_percentage.py` sums `-1` as zero |

```bash
cd NADaymet/dataProduct_DOI

python3 extend_na_mask_open_water.py --dry-run
python3 extend_na_mask_open_water.py --update-landtype18
python3 extend_na_mask_open_water.py --patch-only --only-missing   # if needed
```

**Great Lakes bbox after fix (GeoTIFF stage):** `na_mask==0` dropped from 73.7% to 0.1% of fill cells; `landtype18_count > 0` rose from 16,353 to 180,916. Surfdata NetCDF unchanged until pipeline rebuild.

## Post-processing fix (current surfdata release)

`fix_great_lakes_lake_mask.py` rebuilds lake land units **inside buffered Great Lakes polygons** (Natural Earth 10 m lakes) and on **shoreline fringe** fill cells:

```
lake_count      += wetland14_count   (where class-14 counts exist)
lake_count       = water18_count     (where class-18 counts exist)
open-water holes = 100% lake         (inside buffered mask, no class signal)
PCT_* recomputed from updated counts
```

Implementation notes:

- Class counts sampled with **Daymet projected x/y** (meters), not lon/lat.
- Default **15 km polygon buffer** covers lake extremities.
- Shoreline fringe pass handles fill cells outside the buffer but inside the Great Lakes bounding box.

### Usage

```bash
cd NADaymet/dataProduct_DOI

python3 diagnose_great_lakes_pipeline_gap.py \
  --surfdata-file /path/to/surfdata...c260128.nc

python3 fix_great_lakes_lake_mask.py \
  --in-file  ./surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc \
  --out-file ./surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc \
  --landtype14-tif ../landtype14_count_in_namask.tif \
  --buffer-m 15000
```

## Remaining pipeline work

1. ~~Expand `na_mask` for inland open water~~ — **done** (`extend_na_mask_open_water.py`; see `README_NA_Mask_Open_Water_Fix.md`)
2. ~~Sum PFT counts treating `-1` as zero~~ — **done** (`ELM_PFTs/pft_total_count_percentage.py`)
3. **Rebuild surfdata** from updated GeoTIFFs (class counts → PFT combine → crop → surfdata)
4. Allow lake-only cells (`lake_count > 0`, all PFT counts zero) to receive valid `PCT_LAKE` without requiring vegetation counts (verify after rebuild)
5. Regenerate paper figures from new base surfdata; update `scientific_data_descriptor.tex` Methods
