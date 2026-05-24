# Upstream fix: extend `na_mask` for inland open water

**Date:** 2026-05-22  
**Canonical copy:** `NA_surfdataGEN/NADaymet/dataProduct_DOI/README_NA_Mask_Open_Water_Fix.md`

This note summarizes pipeline changes applied **before** rebuilding surfdata. The current paper product (`surfdata...c260128.nc` and `great_lakes_fix.nc`) still reflects the old pipeline until the rebuild steps below are completed.

---

## What changed

1. **`na_mask.tif` extended** — 228,169 open-water 1 km cells (30 m centre class 18) changed from `mask=0` to `mask=1`.
2. **`landtype18_count_in_namask.tif` patched** — class-18 pixel counts written for all newly opened cells.
3. **`pft_total_count_percentage.py` fixed** — PFT totals treat `-1` sentinels as zero.

Script: `NA_surfdataGEN/NADaymet/dataProduct_DOI/extend_na_mask_open_water.py`

---

## Great Lakes impact (GeoTIFF stage)

| Metric | Before | After |
|--------|--------|-------|
| GL bbox cells with `na_mask==0` | 164,878 (73.7%) | **315 (0.1%)** |
| GL bbox cells with `landtype18_count > 0` | 16,353 | **180,916** |
| Lake Michigan centre (`na` / `t18`) | 0 / −1 | **1 / 1190** |

Existing surfdata NetCDF still shows 223,803 fill cells until the pipeline is rebuilt.

---

## Next steps

See the canonical README for the full rebuild checklist (class counts → PFT combine → surfdata → figure regeneration).

Related post-processing (current release): `Great_Lakes_Open_Water_Report.md`, `fix_great_lakes_lake_mask.py`.
