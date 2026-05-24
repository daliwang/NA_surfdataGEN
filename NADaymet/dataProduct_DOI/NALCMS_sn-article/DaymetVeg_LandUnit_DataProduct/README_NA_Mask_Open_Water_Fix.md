# Upstream fix: extend `na_mask` for inland open water

**Date:** 2026-05-22 (mask fix); 2026-05-24 (full rebuild through `c260524`)  
**Status:** **Complete** — stamped surfdata `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260524.nc`  
**Related:** `README_Great_Lakes_Lake_Fix.md`, `Great_Lakes_Open_Water_Report.md`

---

## Summary

Open-lake 1 km grid cells were excluded from the NALCMS counting pipeline because `na_mask.tif` marked them as `mask=0`. `class_count_na_para.py` only aggregates 30 m pixels inside `na_mask==1` cells, so class-18 (Water) counts never entered `landtype18_count_in_namask.tif` and lake fractions were missing in downstream surfdata.

This change **extends `na_mask` upstream** so inland open-water cells are counted, and patches class-18 pixel counts for the newly opened cells. A companion one-line fix in `pft_total_count_percentage.py` prevents negative PFT totals on water-dominated cells that were already inside the mask.

The post-processing script `fix_great_lakes_lake_mask.py` remains useful for the current surfdata release and for shoreline fringe cells until the full pipeline is rebuilt.

---

## Root cause (recap)

| Step | Issue |
|------|--------|
| 30 m NALCMS source | Great Lakes and other inland open water = **class 18 (Water)** |
| `na_mask.tif` | Many open-lake 1 km cells = **`mask=0`** (outside “active” domain) |
| `class_count_na_para.py` | Skips `mask=0` cells → `landtype18_count_in_namask.tif` stays **`-1`** |
| `pft_total_count_percentage.py` | Summed **`-1`** PFT sentinels → **`pft_total_count = -22`** on water-only cells inside mask |
| Surfdata assembly | Non-positive totals → `PCT_LAKE = NaN`, int16 fill **`-32767`** |

Run `diagnose_great_lakes_pipeline_gap.py` on uncorrected surfdata to reproduce pre-fix statistics.

---

## Changes applied (2026-05-22)

### 1. New script: `extend_na_mask_open_water.py`

**Location:** `NADaymet/dataProduct_DOI/extend_na_mask_open_water.py`

**Logic:**

- For each 1 km cell with `na_mask==0`, sample the 30 m NALCMS source at the **cell centre** (projected Daymet coordinates).
- If the centre pixel is **class 18**, set `na_mask=1`.
- Optionally patch `landtype18_count_in_namask.tif` for newly opened cells using the same polygon aggregation as `class_count_na_para.py`.

**CLI options:**

| Flag | Purpose |
|------|---------|
| `--dry-run` | Report cell counts only; do not write files |
| `--update-landtype18` | Patch class-18 counts after updating the mask |
| `--patch-only` | Re-count class 18 for cells opened since `na_mask.tif.bak` |
| `--only-missing` | With `--patch-only`, skip cells that already have `t18 > 0` |
| `--method center` | Default: centre-pixel class test (fast) |
| `--method zonal` | Blockwise fraction of class 18 inside each cell (`--min-fraction`) |

**Commands run:**

```bash
cd NADaymet/dataProduct_DOI

# Preview
python3 extend_na_mask_open_water.py --dry-run

# Apply mask + patch all newly opened cells
python3 extend_na_mask_open_water.py --update-landtype18

# Re-patch cells that received zero counts after an indexing bug fix
python3 extend_na_mask_open_water.py --patch-only --only-missing
```

### 2. Files modified on disk

| File | Change |
|------|--------|
| `NADaymet/entire_domain/na_mask.tif` | **+228,169** cells set to `mask=1` |
| `NADaymet/na_mask.tif` | Same update (root copy) |
| `NADaymet/entire_domain/na_mask.tif.bak` | Original mask (pre-fix) |
| `NADaymet/na_mask.tif.bak` | Original mask (pre-fix) |
| `NADaymet/landtype18_count_in_namask.tif` | Class-18 counts written for all 228,169 newly opened cells |

**Mask totals:**

| | Before | After |
|---|--------|-------|
| Active cells (`mask==1`) | 21,257,202 | **21,485,371** |
| Inactive cells (`mask==0`) | 44,593,218 | **44,365,049** |

### 3. Code fix: `pft_total_count_percentage.py`

**Location:** `NADaymet/ELM_PFTs/pft_total_count_percentage.py`

Per-class count rasters use `-1` as a masked placeholder. The total-count step now treats sentinels as zero:

```python
for arr in pft_count_vars.values():
    pft_total_count += np.where(arr >= 0, arr, 0)
```

This prevents water-dominated cells **already inside `na_mask`** from accumulating `pft_total_count = -22` before lake/urban/glacier counts are combined.

---

## Verification (Great Lakes bounding box)

Diagnostic target: uncorrected surfdata  
`surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc`  
bbox: lon −92° to −76°, lat 41° to 49°

| Metric | Before fix | After `na_mask` + `landtype18` patch |
|--------|------------|----------------------------------------|
| Fill cells missing `PCT_LAKE` (in surfdata) | 223,803 | 223,803 *(unchanged — surfdata not rebuilt)* |
| `na_mask==0` on those cells | 164,878 (73.7%) | **315 (0.1%)** |
| `na_mask==1` on those cells | 58,925 (26.3%) | **223,488 (99.9%)** |
| `landtype18_count > 0` | 16,353 | **180,916** |
| Lake Michigan centre: `na_mask` / `t18` / src | 0 / −1 / 18 | **1 / 1190 / 18** |
| Lake Superior centre: `na_mask` / `t18` / src | 0 / −1 / 18 | **1 / 1089 / 18** |
| Lake Huron centre: `na_mask` / `t18` / src | 0 / −1 / 18 | **1 / 1190 / 18** |
| Newly opened cells with `t18 > 0` | — | **228,169 / 228,169 (100%)** |

```bash
python3 diagnose_great_lakes_pipeline_gap.py \
  --surfdata-file /path/to/surfdata...c260128.nc
```

**Note:** The diagnostic still reports missing `PCT_LAKE` in the **existing** surfdata NetCDF because that file was built from the old mask. GeoTIFF-stage inputs are fixed; the NetCDF product awaits a pipeline rebuild.

---

## Open-water inclusion criterion

**Default (`--method center`):** a previously masked-out 1 km cell is opened if the 30 m NALCMS pixel at the cell centre is class 18.

**Domain-wide impact:** 228,169 cells opened across the full Daymet 1 km grid (not only the Great Lakes). Atlantic and Pacific offshore samples at `na_mask==0` use non-18 classes at centre (e.g. 0 or 127), so they are **not** added incorrectly.

**Residual gaps:** ~315 Great Lakes bbox cells remain `na_mask==0` (mixed shoreline / non-18 centre pixels). These may still need the post-processing fix or a lower `--min-fraction` zonal pass.

---

## Relationship to post-processing fix

| Approach | Script | When to use |
|----------|--------|-------------|
| **Upstream (this fix)** | `extend_na_mask_open_water.py` | Correct GeoTIFF inputs before count aggregation and surfdata build |
| **Post-processing** | `fix_great_lakes_lake_mask.py` | Correct an existing surfdata NetCDF; handles wetland-14 → lake transfer and 100% lake holes inside buffered Great Lakes polygons |

After a full pipeline rebuild with the updated `na_mask`, the post-processor should only be needed for:

- Remaining shoreline fringe cells outside the centre-pixel criterion
- Wetland-14 → lake reclassification inside Great Lakes polygons (if still desired)
- Backward compatibility with `c260128.nc` until a new base surfdata is published

---

## Next steps (pipeline rebuild)

### Completed (2026-05-24)

1. **Full class-18 re-count** (~98 min):
   ```bash
   cd NADaymet
   python3 class_count_na_para.py nalcms_18_Water.tif
   ```
   Output: `landtype18_count_in_namask.tif` (backup: `landtype18_count_in_namask.tif.prepatch.bak`).

2. **Sanity check:** classes 1–17 and 19 on the 228,169 newly opened cells were all `-1` at 30 m centre (100% class 18). Full re-count of those classes is **not** required.

3. **Minimal Phase 1 prep** via `prepare_open_mask_cells.py`:
   - Patched `-1 → 0` on classes 1–17, 19 for new cells only
   - Rebuilt `landtypes_count/landtype18_nalcms_Water_in_daymet.nc`
   - Rebuilt `ELM_PFT_output/lake_landtype18_nalcms_Water_in_daymet.nc`

4. **Phase 2 PFT combine** (see runbook for symlink note):
   - `combine_pft_counts.py` → `pft_total_count_percentage.py` → `pft_urban_lake_glacier_percentage.py`
   - `make_land_veg_urban_lake_glacier_percentage.py`
   - **Checkpoint:** all 228,169 new cells have `lake_count > 0`, `lake_percentage = 100%`, `pft_total_count = 0` (no `-22` bug).

### Completed (2026-05-24) — full rebuild

5. **Phases 3–4:** cropped, merged, and built final surfdata:
   ```
   surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260524.nc
   ```
   Location: `NADaymet/dataProduct_DOI/`

6. **Phase 5 validation:**
   - Great Lakes fill cells: **954** (down from 223,803 on `c260128`)
   - `PCT_LAKE == 100%` in Great Lakes bbox: **227,547** (up from 4,698)
   - Internal validation: 0 PFT / land-unit closure failures

### Optional follow-ups

1. **Regenerate paper figures** from `c260524.nc` (Figure 5 RGB map, Li et al. comparison panels).

2. **Update manuscript** (`scientific_data_descriptor.tex`) Methods / Technical Validation to describe the upstream mask extension.

3. **Post-processing** (`fix_great_lakes_lake_mask.py`) — only if shoreline fringe or wetland-14 → lake transfer is still desired (~954 residual fill cells).

**Full step-by-step runbook:** `REPORT_Surfdata_Rebuild_5_Phase_Runbook.md`

---

## File index

| File | Role |
|------|------|
| `extend_na_mask_open_water.py` | Extend `na_mask`; patch `landtype18_count_in_namask.tif` |
| `prepare_open_mask_cells.py` | Minimal Phase 1 after mask-only fix (patch sentinels, rebuild lake NC) |
| `diagnose_great_lakes_pipeline_gap.py` | Reproducible before/after diagnostic |
| `fix_great_lakes_lake_mask.py` | Post-processing surfdata correction (existing release) |
| `class_count_na_para.py` | Per-class 30 m → 1 km counting (uses `na_mask`) |
| `ELM_PFTs/pft_total_count_percentage.py` | PFT total with `-1` sentinel fix |
| `entire_domain/na_mask.tif` | Updated 1 km active-domain mask |
| `entire_domain/na_mask.tif.bak` | Pre-fix backup |
| `landtype18_count_in_namask.tif` | Patched class-18 pixel counts |

---

## Implementation notes

- **Coordinate systems:** all sampling uses Daymet projected **x/y in metres** (Lambert Conformal Conic), consistent with `class_count_na_para.py` and `fix_great_lakes_lake_mask.py`. Do not index 30 m rasters with 1 km row/col indices.
- **Class-18 counting:** the landtype18 patch uses `rio_mask` per cell (same box convention as `class_count_na_para.py`), not block sub-array slicing, to avoid transform alignment errors.
- **Backups:** original masks are preserved as `na_mask.tif.bak`. To restore: `cp na_mask.tif.bak na_mask.tif`.
