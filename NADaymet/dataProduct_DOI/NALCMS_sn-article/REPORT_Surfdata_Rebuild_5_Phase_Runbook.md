# Surfdata rebuild runbook (5 phases)

**Purpose:** Repeatable procedure to rebuild the Daymet NALCMS surfdata product after upstream fixes (especially `na_mask` open-water extension).  
**Repo:** `NA_surfdataGEN`  
**Branch:** `NALCMS2DAYMET__SURF_VegMapLandUnit`  
**Related docs:** `README_NA_Mask_Open_Water_Fix.md`, `README_VegMapLandUnit_Rebuild.md`, `command.txt`

---

## Before you start

### Root paths (edit if your clone differs)

```bash
export REPO=/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN
export NAD=$REPO/NADaymet
export DOI=$NAD/dataProduct_DOI
export PFT=$NAD/ELM_PFTs
export PFT_OUT=$PFT/ELM_PFT_output
export ENT=$NAD/entire_domain
export PAPER=$REPO/NADaymet/dataProduct_DOI/NALCMS_sn-article   # figure/validation scripts mirror
```

### Prerequisites

| Item | Location | Notes |
|------|----------|--------|
| Extended `na_mask` | `entire_domain/na_mask.tif`, `NADaymet/na_mask.tif` | Backup: `na_mask.tif.bak` |
| Patched class-18 counts | `NADaymet/landtype18_count_in_namask.tif` | From `extend_na_mask_open_water.py` |
| 30 m NALCMS source | `entire_domain/nalcms2daymet_hcompressed.tif` | Class 18 = open water |
| Surfdata template | `DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc` | Grid reference |
| MTCO temperature | `PFT/mean_temperature_coldest_month.nc` | Phase 4 |
| Python deps | `rasterio`, `netCDF4`, `xarray`, `numpy`, `geopandas` (diagnostics only) | |

### Phase 0 — Upstream mask fix (already applied)

Run once when open-lake cells are missing from the mask:

```bash
cd $DOI

python3 extend_na_mask_open_water.py --dry-run
python3 extend_na_mask_open_water.py --update-landtype18

# If landtype18 patch needs a redo:
python3 extend_na_mask_open_water.py --patch-only --only-missing
```

**Success checks:**

```bash
python3 diagnose_great_lakes_pipeline_gap.py \
  --surfdata-file $PAPER/../DaymetVeg_LandUnit_DataProduct/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc
```

- Great Lakes bbox: `na_mask==0` ≪ 1% of fill cells (was ~74% before fix)
- Lake centres: `na_mask=1`, `landtype18_count > 0`
- Existing surfdata NetCDF still shows gaps until Phases 1–4 complete

---

## Phase 1 — Refresh count layers

**Goal:** Propagate updated `na_mask` and `landtype18_count_in_namask.tif` into NetCDF count files used by the PFT / lake combine step.

### 1a. (Optional) Full class-count rebuild

Skip if you only changed open-water cells and already patched `landtype18_count_in_namask.tif`.

```bash
cd $NAD

# One class at a time; input GeoTIFFs live in entire_domain/
python3 class_count_na_para.py nalcms_18_Water.tif
# python3 class_count_na_para.py nalcms_14_Wetland.tif
# ... nalcms_1 through nalcms_19 as needed
```

Outputs: `NADaymet/landtype{N}_count_in_namask.tif` (1 km pixel counts per class).

### 1b. Convert count GeoTIFFs → landtype NetCDFs

```bash
cd $NAD/landtypes_count

# Symlink or copy count tifs from parent NADaymet/ if running here
# ln -sf ../landtype18_count_in_namask.tif .

python3 landtype_tif2nc.py
```

**Note:** `landtype_tif2nc.py` opens a matplotlib window per class (`plt.show()`). For a headless/automated run, convert class 18 only in Python or temporarily comment out the plot block.

Produces: `landtype18_nalcms_Water_in_daymet.nc` (and siblings for other classes).

**Minimum for lake fix:** regenerate **class 18** (and ideally 17 urban, 19 glacier if those layers are stale).

### 1c. Build lake / urban / glacier PFT-layer NetCDFs

```bash
cd $PFT

python3 batch_create_pft_nc.py
```

For direct land units (no climate split), this writes e.g.:

- `ELM_PFT_output/lake_landtype18_nalcms_Water_in_daymet.nc`
- `ELM_PFT_output/urban_landtype17_nalcms_Urban_in_daymet.nc`
- `ELM_PFT_output/glacier_landtype19_nalcms_Snow_Ice_in_daymet.nc`

Vegetation classes produce `pft*.nc` files used in Phase 2.

### 1d. Minimal path after mask-only fix (recommended)

When only **228,169** cells changed (`na_mask` 0→1) and class-18 was fully re-counted, skip full 1–19 re-count and use:

```bash
cd $DOI

python3 prepare_open_mask_cells.py --dry-run
python3 prepare_open_mask_cells.py
```

This script:

1. Sets `-1 → 0` on `landtype{1-17,19}_count_in_namask.tif` for newly opened cells only.
2. Writes `landtypes_count/landtype18_nalcms_Water_in_daymet.nc`.
3. Rebuilds `ELM_PFT_output/lake_landtype18_nalcms_Water_in_daymet.nc`.
4. Zeros `urban_count` / `glacier_count` on new cells in existing ELM PFT NetCDFs.

**Sanity check (2026-05-24):** full re-count of classes 1–17 and 19 is **not** required — new cells are 100% class-18 water at 30 m centre; only class 18 needed a full re-count (~98 min via `class_count_na_para.py`).

### Phase 1 checkpoint

```bash
python3 << PYEOF
import rasterio
from pathlib import Path
t18 = Path("${NAD}/landtype18_count_in_namask.tif")
with rasterio.open(t18) as s:
    d = s.read(1)
print("landtype18 cells with count > 0:", (d > 0).sum())
print("max count:", d.max())
PYEOF
```

Expect **228,169+** water-dominated cells with positive class-18 counts after the mask fix.

---

## Phase 2 — Rebuild PFT and land-unit combine

**Goal:** Assemble `PCT_LAKE`, `PCT_NATVEG`, urban, glacier from pixel counts. Uses fixed `pft_total_count_percentage.py` (`-1` sentinels treated as zero).

```bash
cd $PFT

# combine_pft_counts.py reads pft*.nc from $PFT cwd; per-landtype files live in ELM_PFT_output/
for f in "$PFT_OUT"/pft*_landtype*.nc; do ln -sf "$f" .; done
# Do NOT symlink cropped percentage files (e.g. pft_total_count_percentage.cropped_to_surfdata.nc)

# Backup previous outputs (optional)
mv $PFT_OUT/combined_pft_count.nc $PFT_OUT/combined_pft_count.bak.nc 2>/dev/null || true
mv $PFT_OUT/pft_total_count_percentage.nc $PFT_OUT/pft_total_count_percentage.bak.nc 2>/dev/null || true
mv $PFT_OUT/combined_pft_urban_lake_glacier_total_count.nc $PFT_OUT/combined_pft_urban_lake_glacier_total_count.bak.nc 2>/dev/null || true

python3 combine_pft_counts.py
python3 pft_total_count_percentage.py
python3 pft_urban_lake_glacier_percentage.py
```

```bash
cd $DOI

python3 make_land_veg_urban_lake_glacier_percentage.py \
  --in  $PFT_OUT/combined_pft_urban_lake_glacier_total_count.nc \
  --out $DOI/land_veg_urban_lake_glacier_percentage.nc
```

### Phase 2 outputs

| File | Variables |
|------|-----------|
| `ELM_PFT_output/combined_pft_count.nc` | Per-PFT counts |
| `ELM_PFT_output/pft_total_count_percentage.nc` | PFT totals + percentages |
| `ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.nc` | `lake_count`, `urban_count`, `glacier_count`, `pft_total_count` |
| `land_veg_urban_lake_glacier_percentage.nc` | Counts + `lake_percentage`, `pft_percentage`, etc. |

### Phase 2 checkpoint

Inspect a Great Lakes cell in `combined_pft_urban_lake_glacier_total_count.nc`: open-lake interiors should have **`lake_count > 0`** and **`pft_total_count ≥ 0`** (not `-22`).

```bash
python3 << 'PYEOF'
import numpy as np, rasterio
from netCDF4 import Dataset
from pathlib import Path
nad = Path("${NAD}")
with rasterio.open(nad/"entire_domain/na_mask.tif.bak") as o, rasterio.open(nad/"entire_domain/na_mask.tif") as n:
    opened = (o.read(1)==0) & (n.read(1)==1)
with Dataset(nad/"ELM_PFTs/ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.nc") as nc:
    lake, pft = nc.variables["lake_count"][0], nc.variables["pft_total_count"][0]
print("new cells:", opened.sum(), "lake>0:", (lake[opened]>0).sum(), "pft==-22:", (pft[opened]==-22).sum())
PYEOF
```

**Expected on 228,169 newly opened cells (2026-05-24):** `lake_count > 0` on all; `pft_total_count = 0`; `lake_percentage = 100%`; zero cells with `pft_total_count = -22`.

---

## Phase 3 — Crop to surfdata grid

**Goal:** Align large Daymet count grids to the surfdata template window (`dx=98`, `dy=72`).

```bash
cd $DOI

SURF=$DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc
DX=98
DY=72

# Land-unit percentages (lake, veg, urban, glacier)
python3 crop_align_merge.py \
  --surf-file $SURF \
  --land-file  $DOI/land_veg_urban_lake_glacier_percentage.nc \
  --dx $DX --dy $DY \
  --out-cropped $DOI/land_veg_urban_lake_glacier_percentage.cropped_to_surfdata.nc

# PFT breakdown
python3 crop_align_merge.py \
  --surf-file $SURF \
  --land-file  $PFT_OUT/pft_total_count_percentage.nc \
  --dx $DX --dy $DY \
  --out-cropped $PFT_OUT/pft_total_count_percentage.cropped_to_surfdata.nc

# Combined counts
python3 crop_align_merge.py \
  --surf-file $SURF \
  --land-file  $PFT_OUT/combined_pft_urban_lake_glacier_total_count.nc \
  --dx $DX --dy $DY \
  --out-cropped $PFT_OUT/combined_pft_urban_lake_glacier_total_count.cropped_to_surfdata.nc
```

---

## Phase 4 — Build final surfdata NetCDF

**Goal:** Produce stamped `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.cYYMMDD.nc` with maps, counts, and MTCO.

```bash
cd $DOI

# Merge land fractions into surfdata shell
python3 crop_align_merge.py \
  --surf-file $DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc \
  --land-file $DOI/land_veg_urban_lake_glacier_percentage.cropped_to_surfdata.nc \
  --dx 0 --dy 0 \
  --out-cropped /tmp/noop.nc \
  --out-merged  $DOI/surfdata_with_land_veg_urban_lake_glacier.nc

# Add mean temperature of coldest month
python3 add_temp_to_surfdata.py \
  --surf-file $DOI/surfdata_with_land_veg_urban_lake_glacier.nc \
  --temp-file $PFT/mean_temperature_coldest_month.nc \
  --out-file  $DOI/surfdata_with_land_veg_urban_lake_glacier_temp.nc

# Optional: fix projected x/y units on legacy files
python3 fix_xy_units.py \
  --in  $DOI/surfdata_with_land_veg_urban_lake_glacier_temp.nc \
  --out $DOI/surfdata_with_land_veg_urban_lake_glacier_temp.fixed_units.nc

# Float32 compressed intermediate
python3 convert_surfdata_float32.py \
  --in  $DOI/surfdata_with_land_veg_urban_lake_glacier_temp.nc \
  --out $DOI/NA_surfdata_nalcms2daymet_pft_landunit_temp.nc \
  --level 5

# Final VegMapLandUnit surfdata (date-stamped filename)
python3 build_vegmap_surfdata_from_combined.py \
  --template $DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc \
  --combined $DOI/NA_surfdata_nalcms2daymet_pft_landunit_temp.nc \
  --pft-breakdown $PFT_OUT/pft_total_count_percentage.cropped_to_surfdata.nc \
  --counts $PFT_OUT/combined_pft_urban_lake_glacier_total_count.cropped_to_surfdata.nc \
  --out $DOI/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.nc \
  --with-date-stamp --stamp-format c%y%m%d
```

**Record the output filename**, e.g. `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc`.

### Phase 4 checkpoint

```bash
NEW_SURF=$DOI/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc   # adjust date

python3 $DOI/diagnose_great_lakes_pipeline_gap.py --surfdata-file $NEW_SURF
```

**Expected after full rebuild:**

- Few or no Great Lakes fill cells (`PCT_LAKE` missing)
- Valid `PCT_LAKE` at lake centres without post-processing

---

## Phase 5 — Validate and regenerate paper artifacts

### 5a. Internal validation (closure metrics)

```bash
python3 $PAPER/internal_validation/compute_internal_validation.py \
  --final-nc $NEW_SURF
```

Review:

- `internal_validation/results/summary_metrics.csv`
- `internal_validation/results/internal_validation_summary.md`

Compare uncorrected vs new file:

```bash
python3 $PAPER/internal_validation/compute_internal_validation.py \
  --final-nc $DOI/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc \
  --skip-class-count-closure
```

### 5b. Quick surfdata plots

```bash
python3 $REPO/validate_visualize_surfdata.py \
  --file $NEW_SURF \
  --vars PCT_NATVEG PCT_LAKE PCT_URBAN PCT_GLACIER AvgTempColdMonth \
  --validate --stats --plot --save \
  --outdir $DOI/figures_new/surfdata_figs \
  --coarsen 1
```

### 5c. Paper figures (optional)

Point scripts at `$NEW_SURF` (edit defaults or use CLI flags):

```bash
cd $PAPER/PaperFigures/scripts

python3 generate_landtype_rgb.py          # Figure 5 RGB map
python3 generate_li_lulc_comparison.py    # Li et al. 2020 panels
python3 generate_e3sm_landuse_comparison.py
python3 generate_pft_panel.py
python3 generate_mtco_plots.py
```

Copy outputs to the paper workspace if you edit figures there.

### 5d. Manuscript

Update `scientific_data_descriptor.tex` Methods / Technical Validation to note upstream `na_mask` extension (see `README_NA_Mask_Open_Water_Fix.md`).

---

## Appendix A — Post-processing (usually not needed after rebuild)

The old workflow applied **`fix_great_lakes_lake_mask.py`** to `c260128.nc` because open-lake cells were never counted. After Phases 1–4, try the new surfdata **first**:

```bash
python3 $DOI/fix_great_lakes_lake_mask.py \
  --in-file  $NEW_SURF \
  --out-file ${NEW_SURF%.nc}.great_lakes_fix.nc \
  --landtype14-tif $NAD/landtype14_count_in_namask.tif \
  --buffer-m 15000
```

Use post-processing only if diagnostics still show shoreline fringe gaps or wetland-14 → lake transfer is desired inside Great Lakes polygons.

---

## Appendix B — One-page flowchart

```
Phase 0  extend_na_mask_open_water.py  →  na_mask.tif, landtype18_count_in_namask.tif
              ↓
Phase 1  class_count (opt) → prepare_open_mask_cells.py  OR  landtype_tif2nc → batch_create_pft_nc
              ↓
Phase 2  symlink pft*_landtype*.nc → combine_pft_counts → pft_total_count_percentage → pft_urban_lake_glacier_percentage
         → make_land_veg_urban_lake_glacier_percentage.nc
              ↓
Phase 3  crop_align_merge (×3)  [dx=98, dy=72]
              ↓
Phase 4  merge surfdata → add_temp → convert_float32 → build_vegmap_surfdata_from_combined
              ↓
Phase 5  diagnose_great_lakes_pipeline_gap, compute_internal_validation, figure scripts
```

---

## Appendix C — Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| `PCT_LAKE` still NaN in Great Lakes | Phase 2 not rerun; stale `lake_landtype18*.nc` | Repeat Phase 1c + Phase 2 |
| `pft_total_count = -22` on water cells | Old `pft_total_count_percentage.py` | Confirm `-1` → 0 fix is committed |
| `patch-only: 0 cells` | Already patched | Expected; use `--patch-only` without `--only-missing` to force recount |
| `landtype18` still `-1` | Mask not extended | Rerun Phase 0 |
| Cropped arrays misaligned | Wrong template or dx/dy | Use `c251202.nc`, dx=98, dy=72 |
| `combine_pft_counts` shape mismatch | Symlinked cropped percentage NC | Link only `pft*_landtype*.nc` from `ELM_PFT_output/` |

---

## Appendix D — File index

| Phase | Script | Directory |
|-------|--------|-----------|
| 0 | `extend_na_mask_open_water.py`, `diagnose_great_lakes_pipeline_gap.py` | `dataProduct_DOI/` |
| 1 | `prepare_open_mask_cells.py` (minimal path) | `dataProduct_DOI/` |
| 1 | `class_count_na_para.py` | `NADaymet/` |
| 1 | `landtype_tif2nc.py` | `landtypes_count/` |
| 1 | `batch_create_pft_nc.py` | `ELM_PFTs/` |
| 2 | `combine_pft_counts.py`, `pft_total_count_percentage.py`, `pft_urban_lake_glacier_percentage.py` | `ELM_PFTs/` |
| 2 | `make_land_veg_urban_lake_glacier_percentage.py` | `dataProduct_DOI/` |
| 3–4 | `crop_align_merge.py`, `add_temp_to_surfdata.py`, `convert_surfdata_float32.py`, `build_vegmap_surfdata_from_combined.py` | `dataProduct_DOI/` |
| 5 | `compute_internal_validation.py`, `PaperFigures/scripts/*.py` | `NALCMS_sn-article/` mirror |

---

## Appendix E — Execution log (2026-05-24)

| Step | Status | Notes |
|------|--------|-------|
| Phase 0 `extend_na_mask_open_water.py` | Done (2026-05-22) | +228,169 cells |
| Full class-18 re-count | Done (~98 min) | `landtype18_count_in_namask.tif`; backup `.prepatch.bak` |
| Sanity: classes 1–17, 19 on new cells | Done | All were `-1`; patch to 0 sufficient |
| `prepare_open_mask_cells.py` | Done | 228,169 cells patched per class; lake NC rebuilt |
| Phase 2 PFT combine | Done | Checkpoint: 100% lake on new cells; no `-22` totals |
| Phase 3–4 surfdata rebuild | Done (2026-05-24) | `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260524.nc` (508 MB) |
| Phase 5 validation / figures | Partial | Internal validation passed; figure scripts not rerun |

### c260524 vs c260128 (Great Lakes bbox)

| Metric | c260128 | c260524 |
|--------|---------|---------|
| `PCT_LAKE == 100%` cells | 4,698 | **227,547** |
| `PCT_LAKE > 0` cells | 338,440 | **561,289** |
| Fill cells (`total_count = -32767`, NaN lake) | 223,803 | **954** |

Internal validation: **0** PFT closure failures, **0** land-unit closure failures on 21.36M valid land cells.

---

*Last updated: 2026-05-24. Full rebuild complete through Phase 5 validation; stamped product `c260524`.*
