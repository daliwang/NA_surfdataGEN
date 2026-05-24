# Great Lakes Open-Water Classification Report

**Date:** 2026-05-22 (updated with upstream `na_mask` fix)  
**Dataset:** `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc`  
**Corrected file:** `../DaymetVeg_LandUnit_DataProduct/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc`  
**Figure:** `landtype_rgb_map.png` (Figure 5 in `scientific_data_descriptor.tex`)  
**Upstream fix doc:** `NA_surfdataGEN/NADaymet/dataProduct_DOI/README_NA_Mask_Open_Water_Fix.md`

---

## Executive summary

Open water in the Great Lakes appeared as white gaps (no-data / ocean) in the 1-km NALCMS-derived surfdata product and in the paper’s integrated land-unit RGB map. The 30 m NALCMS source (`nalcms2daymet_hcompressed.tif`) correctly maps open-lake pixels as **class 18 (Water)**. The gaps arise from the **counting and surfdata assembly pipeline**:

1. **`na_mask` exclusion:** Many open-lake 1 km cells have `na_mask=0`. `class_count_na_para.py` only aggregates 30 m pixels where `na_mask==1`, so class-18 counts never enter the 1 km count rasters (`landtype18_count_in_namask.tif` stays `-1`).
2. **Negative PFT sentinels:** Water-dominated cells inside `na_mask` can still fail when `pft_total_count` sums `-1` placeholders across PFT layers, producing invalid totals in combined count files.
3. **Cropping and fill encoding:** Domain cropping to the surfdata grid and int16 fill values (`-32767`) yield `PCT_LAKE = NaN` even when partial class-18 signal exists in count GeoTIFFs.

A post-processing correction reassigns class-14/18 counts to lake inside buffered Great Lakes polygons, extends the fix to cropped shoreline fringe cells, and assigns 100% lake to remaining open-water holes with missing totals.

**Update (2026-05-22):** An upstream fix now extends `na_mask.tif` to include inland open-water cells (30 m class 18 at 1 km centre) and patches `landtype18_count_in_namask.tif`. See **`README_NA_Mask_Open_Water_Fix.md`**. The surfdata NetCDF has not yet been rebuilt from these inputs; this report’s before/after surfdata statistics refer to the post-processing correction on `c260128.nc`.

---

## Problem description

### Symptom

In `PaperFigures/landtype_rgb_map.png`, the integrated RGB map encodes:

| Channel | Land unit |
|---------|-----------|
| Green   | `PCT_NATVEG` |
| Red     | `PCT_URBAN` (summed layers) |
| Blue    | `PCT_LAKE` |
| Gray blend | `PCT_GLACIER` |
| White   | Ocean / no land unit present |

Before correction, the Great Lakes showed large **white interior patches** (especially Lake Superior, northern Lake Michigan, and Lake Huron), even though surrounding lake shorelines appeared blue or green. This was inconsistent with other large North American lakes (e.g., Great Bear Lake, Lake Winnipeg), which rendered correctly in blue.

### Why white appears in the RGB map

The plotting script (`PaperFigures/scripts/generate_landtype_rgb.py`) marks a grid cell as land only when the sum of vegetation, lake, urban, and glacier fractions is greater than zero. Cells with missing or all-zero fractions are set to white:

```python
land_present = (veg + lake + urban + glacier) > 0
rgb[~land_present] = 1.0  # white background
```

Any cell with `PCT_LAKE = NaN`, `PCT_NATVEG = NaN`, and zero urban/glacier therefore appears as open ocean, even if it lies geographically inside a Great Lake.

---

## Root-cause analysis

### 1. Thirty-metre NALCMS source (class 18 at open lake)

The projected 30 m NALCMS GeoTIFF (`NADaymet/entire_domain/nalcms2daymet_hcompressed.tif`) maps Great Lakes open water as **class 18 (Water)**, not class 14 (Wetland).

**Verification at lake centres:**

| Location | `nalcms2daymet_hcompressed.tif` |
|----------|----------------------------------|
| Lake Superior centre (~−87.0°, 47.5°) | 18 |
| Lake Michigan centre (~−87.0°, 43.5°) | 18 |
| Lake Huron centre (~−82.5°, 44.8°) | 18 |

Class 14 appears mainly near shorelines and in mixed coastal cells (~6% of a Great Lakes bounding-box sample), not in open-lake interiors.

### 2. `na_mask` excludes open-lake grid cells from counting (primary pipeline gap)

Per-class counts are produced by `class_count_na_para.py`, which **only tallies 30 m pixels where `na_mask.tif == 1`**:

```python
output_data = np.full((mask_height, mask_width), -1, dtype=np.int32)
if mask_data[row, col] == 1:
    count = np.sum(out_image == landtype_value)
    output_data[row, col] = count
```

Open-lake 1 km cells typically have **`na_mask = 0`**, so `landtype18_count_in_namask.tif` remains `-1` even when every 30 m pixel in the cell is class 18.

**Diagnostic on uncorrected surfdata (Great Lakes bbox, 223,803 fill cells):**

| Category | Cell count | Share |
|----------|------------|-------|
| `na_mask == 0` (never counted) | 164,878 | 73.7% |
| `na_mask == 1` (inside land mask) | 58,925 | 26.3% |
| `na_mask == 0` and 30 m class 18 at centre | most open-lake interiors | — |
| `na_mask == 1`, class-18 count > 0, surfdata still fill | 16,353 | 7.3% |

Run `NADaymet/dataProduct_DOI/diagnose_great_lakes_pipeline_gap.py` to reproduce these totals.

**After upstream `na_mask` fix (GeoTIFF stage, same GL bbox):**

| Category | Cell count | Share |
|----------|------------|-------|
| `na_mask == 0` (never counted) | **315** | **0.1%** |
| `na_mask == 1` (inside land mask) | **223,488** | **99.9%** |
| `landtype18_count > 0` | **180,916** | — |
| Lake Michigan centre: `na_mask` / `t18` / src | **1 / 1190 / 18** | — |

Surfdata fill-cell count (223,803) is unchanged until the pipeline is rebuilt.

### 3. PFT sentinel summation and combined count assembly

For water-dominated cells inside `na_mask`, `pft_total_count_percentage.py` sums all PFT count layers, each using `-1` as a masked placeholder. Water-only cells therefore accumulate large negative totals (commonly **−22**) before lake, urban, and glacier counts are combined. `pft_urban_lake_glacier_percentage.py` then treats `Total_count <= 0` as non-land and writes `NaN` percentages.

Even when `landtype18_count_in_namask.tif` reports class-18 pixels (e.g. 607 sub-grid pixels), the intermediate `combined_pft_urban_lake_glacier_total_count.nc` can still store `lake_count = total_count = -32767` at the same grid location after int16 encoding and crop.

### 4. Domain cropping to surfdata (secondary propagation)

`crop_align_merge.py` extracts a `(dx, dy)` window from the larger count grid (`dx=98`, `dy=72`) to match the surfdata template. This step preserves missing counts; it does not introduce the `-1`/`-32767` values but maps them into the final product via `build_vegmap_surfdata_from_combined.py`.

### 5. Natural Earth polygon under-coverage (residual gaps addressed by fix)

An initial correction used Natural Earth 10 m lake polygons with a point-in-polygon test. A **15 km buffer** expanded coverage to **302,974 cells**. A further **shoreline fringe** pass applies class-14/18 transfers to fill cells in the Great Lakes bounding box outside the buffered polygon.

### 6. Coordinate sampling bug in early fix attempts (implementation issue)

An early version of the fix script sampled class-14 counts using **geographic lon/lat (degrees)** against GeoTIFFs in **Daymet projected coordinates (meters, Lambert Conformal Conic)**. This produced incorrect count lookups. The corrected script samples using the surfdata `x`/`y` projected grid, consistent with `landtype14_count_in_namask.tif`.

---

## Upstream fix applied (2026-05-22)

Full documentation: **`README_NA_Mask_Open_Water_Fix.md`**

| Change | Detail |
|--------|--------|
| `extend_na_mask_open_water.py` | Sets `na_mask=1` for 228,169 cells with 30 m centre class 18 |
| `landtype18_count_in_namask.tif` | Patched for all newly opened cells |
| `pft_total_count_percentage.py` | `-1` PFT sentinels treated as zero in total count |
| Backups | `na_mask.tif.bak` in `entire_domain/` and `NADaymet/` |

**Next:** rebuild surfdata from updated GeoTIFFs; re-run diagnostics and figure scripts on the new base product.

---

## Correction applied (post-processing)

### Script

`NA_surfdataGEN/NADaymet/dataProduct_DOI/fix_great_lakes_lake_mask.py`

### Logic

For all grid cells inside **buffered Great Lakes polygons** (Natural Earth 10 m lakes + 15 km buffer):

1. **Reclassify class-14 wetland counts as lake:**
   ```
   lake_count      += wetland14_count
   pft_total_count -= wetland14_count
   ```
2. **Use class-18 water counts** where present but lake counts were zero.
3. **Fill cropped open-water holes:** cells inside the mask with no remaining class counts receive `lake_count = 1000` (representative full-cell count), yielding `PCT_LAKE = 100%`.
4. **Recompute** `PCT_LAKE`, `PCT_NATVEG`, and `PCT_NAT_PFT` (PFT 13 reduced in proportion to transferred wetland count).

### Command used

```bash
python3 NA_surfdataGEN/NADaymet/dataProduct_DOI/fix_great_lakes_lake_mask.py \
  --in-file  DaymetVeg_LandUnit_DataProduct/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc \
  --out-file DaymetVeg_LandUnit_DataProduct/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc \
  --landtype14-tif NA_surfdataGEN/NADaymet/landtype14_count_in_namask.tif \
  --buffer-m 15000
```

### NetCDF provenance attributes

The corrected file records:

| Attribute | Value |
|-----------|-------|
| `great_lakes_fix` | Reclassified NALCMS class-14 wetland counts to lake inside buffered Great Lakes polygons (Natural Earth 10m lakes, buffer=15000 m). Assigned 100% lake to cropped open-water cells with missing class counts. |
| `great_lakes_fix_buffer_m` | 15000 |
| `great_lakes_fix_source` | `landtype14_count_in_namask.tif` |
| `great_lakes_fix_script` | `fix_great_lakes_lake_mask.py` |

---

## Results

### Fix statistics (15 km buffer)

| Metric | Value |
|--------|-------|
| Grid cells in buffered Great Lakes mask | 302,974 |
| Cells with wetland-14 → lake transfer | 42,310 |
| NALCMS class-14 pixels reclassified | 11,354,756 |
| White RGB pixels inside corrected mask | **0** |
| `PCT_LAKE == 100` inside corrected mask | 187,499+ |

### Before vs. after (Great Lakes region)

| Metric | Before (`c260128.nc`) | After (`c260128.great_lakes_fix.nc`) |
|--------|----------------------|--------------------------------------|
| `PCT_LAKE == 0` inside lake polygons | many | **0** |
| `PCT_LAKE == 100` (GL bbox) | ~4,900 | **167,709+** |
| `total_count == -32767` (GL bbox) | 223,803 | **0** (inside mask) |
| Lake Michigan center `PCT_LAKE` | NaN or 0 | **100%** |
| Lake Michigan center RGB | white | **blue** `[0, 0, 1]` |

### Figure regeneration

```bash
cd PaperFigures/scripts
python3 generate_landtype_rgb.py
```

Output: `PaperFigures/landtype_rgb_map.png` — Great Lakes open water now appears in blue, consistent with the legend.

---

## Recommendations

### For this paper / data release

- Use **`surfdata...c260128.great_lakes_fix.nc`** for all Great Lakes–sensitive figures and analyses.
- Reference this report when describing the lake land-unit treatment in the Scientific Data descriptor.

### Longer-term pipeline fix

**Partially implemented (2026-05-22):**

1. ~~**Extend `na_mask`** for inland open water (class 18 at 1 km cell centre)~~ — done; see `README_NA_Mask_Open_Water_Fix.md`
2. ~~**Fix PFT total summation** (`-1` → 0)~~ — done in `pft_total_count_percentage.py`
3. **Rebuild surfdata** from updated count GeoTIFFs (pending)
4. **Optional at GeoTIFF stage:** reassign class-14 pixels inside known large-lake masks to class 18 before counting; or add class-14 wetland counts to lake inside Great Lakes at aggregation time

After rebuild, post-processing with `fix_great_lakes_lake_mask.py` should only be needed for shoreline fringe cells and wetland-14 transfer, not open-lake interiors.

---

## File index

| File | Location |
|------|----------|
| Original surfdata | `DaymetVeg_LandUnit_DataProduct/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc` |
| Corrected surfdata | `DaymetVeg_LandUnit_DataProduct/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc` |
| Fix script | `NA_surfdataGEN/NADaymet/dataProduct_DOI/fix_great_lakes_lake_mask.py` |
| Upstream mask fix | `NA_surfdataGEN/NADaymet/dataProduct_DOI/extend_na_mask_open_water.py` |
| Upstream fix README | `NA_surfdataGEN/NADaymet/dataProduct_DOI/README_NA_Mask_Open_Water_Fix.md` |
| RGB figure script | `PaperFigures/scripts/generate_landtype_rgb.py` |
| RGB figure | `PaperFigures/landtype_rgb_map.png` |
| This report (copy) | `DaymetVeg_LandUnit_DataProduct/Great_Lakes_Open_Water_Report.md` |
