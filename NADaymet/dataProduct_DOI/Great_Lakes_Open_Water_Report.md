# Great Lakes Open-Water Classification Report

**Date:** 2026-05-22  
**Base dataset:** `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc`  
**Corrected file:** `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc`  
**Fix script:** `fix_great_lakes_lake_mask.py` (this directory)

---

## Executive summary

Open water in the Great Lakes appeared as white gaps (no-data / ocean) or wetland vegetation in the 1-km NALCMS-derived surfdata product. The root cause is a **chain of three issues**:

1. **NALCMS misclassification:** Great Lakes open water is mapped as **class 14 (Wetland)**, not class 18 (Water).
2. **Pipeline logic:** The NA_surfdataGEN workflow assigns lake fractions from **class-18 counts only**, so class-14 pixels become ELM wetland (PFT 13) or missing land units.
3. **Grid cropping:** Many open-lake cells lost valid pixel counts after Daymet-grid aggregation (`total_count = -32767`), which RGB maps render as white ocean background.

A post-processing correction reclassifies class-14 wetland counts as lake inside buffered Great Lakes polygons and assigns 100% lake to remaining cropped open-water holes. Internal validation confirms **0 land-unit closure failures** in the corrected file.

---

## Problem description

### Symptom

Integrated land-unit RGB maps encode:

| Channel | Land unit |
|---------|-----------|
| Green   | `PCT_NATVEG` |
| Red     | `PCT_URBAN` (summed layers) |
| Blue    | `PCT_LAKE` |
| Gray blend | `PCT_GLACIER` |
| White   | Ocean / no land unit present |

Before correction, the Great Lakes showed large **white interior patches** (especially Lake Superior, northern Lake Michigan, and Lake Huron).

### Why white appears in RGB maps

Cells with missing or all-zero land-unit fractions are rendered white:

```python
land_present = (veg + lake + urban + glacier) > 0
rgb[~land_present] = 1.0  # white background
```

Any cell with `PCT_LAKE = NaN`, `PCT_NATVEG = NaN`, and zero urban/glacier appears as open ocean, even inside a Great Lake.

---

## Root-cause analysis

### 1. NALCMS class assignment (primary cause)

NALCMS assigns **open water in the Great Lakes to class 14 (Wetland)**, not class 18 (Water).

**Verification at Lake Michigan center (~−87.0°, 45.0°):**

| Source | Value |
|--------|-------|
| `nalcms_18_Water.tif` | 0 |
| `nalcms_14_Wetland.tif` | 14 |
| `landtype18_count_in_namask.tif` | 0 |
| `landtype14_count_in_namask.tif` | 306 |

### 2. NA_surfdataGEN pipeline mapping

Class 14 → ELM PFT 13 (wetland); class 18 → lake land unit. `PCT_LAKE` is computed from **class-18 counts only**, so Great Lakes open water never enters the lake land unit through the standard path.

### 3. Missing counts after grid cropping

In the Great Lakes bounding box (roughly 41°–49°N, 92°–76°W), **223,803 cells** had missing lake fractions in the uncorrected file (`total_count = -32767`).

### 4. Natural Earth polygon under-coverage

Strict Natural Earth 10 m lake polygons covered **223,136 grid cells**. A **15 km buffer** expanded coverage to **302,974 cells** and eliminated white holes inside the corrected mask.

### 5. Coordinate sampling (implementation)

Class-14 counts must be sampled with **Daymet projected x/y** (meters), not geographic lon/lat, when reading `landtype14_count_in_namask.tif`.

---

## Correction applied

### Logic

For grid cells inside **buffered Great Lakes polygons** (Natural Earth 10 m lakes + 15 km buffer):

1. Reclassify class-14 wetland counts as lake (`lake_count += wetland14_count`, `pft_total_count -= wetland14_count`).
2. Use class-18 water counts where present but lake counts were zero.
3. Fill cropped open-water holes with a representative full-cell lake count.
4. Recompute `PCT_LAKE`, `PCT_NATVEG`, `PCT_NAT_PFT`, `PCT_URBAN`, and `PCT_GLACIER` from updated counts.

### Command

```bash
python3 fix_great_lakes_lake_mask.py \
  --in-file  ./surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc \
  --out-file ./surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc \
  --landtype14-tif ../landtype14_count_in_namask.tif \
  --buffer-m 15000
```

---

## Results

### Fix statistics (15 km buffer)

| Metric | Value |
|--------|-------|
| Grid cells in buffered Great Lakes mask | 302,974 |
| Cells with wetland-14 → lake transfer | 42,310 |
| NALCMS class-14 pixels reclassified | 11,354,756 |
| Land-unit closure failures (final product) | **0** / 21,323,964 cells |
| PFT closure failures (final product) | 10 (pre-existing edge cases in base file) |

### Before vs. after (Great Lakes region)

| Metric | Before (`c260128.nc`) | After (`great_lakes_fix.nc`) |
|--------|----------------------|------------------------------|
| `PCT_LAKE == 100` (GL bbox) | ~4,900 | **167,709+** |
| `total_count == -32767` (GL bbox) | 223,803 | **0** (inside mask) |
| Lake Michigan center `PCT_LAKE` | NaN or 0 | **100%** |

---

## Recommendations

### Data release

Use **`surfdata...c260128.great_lakes_fix.nc`** for Great Lakes–sensitive figures and ELM simulations.

### Longer-term pipeline fix

1. Reassign class-14 pixels inside known large-lake masks to class 18 before counting; **or**
2. Set `lake_count = class18_count + class14_count_in_great_lakes` during count aggregation.

---

## File index

| File | Location |
|------|----------|
| Fix script | `NADaymet/dataProduct_DOI/fix_great_lakes_lake_mask.py` |
| Quick reference | `NADaymet/dataProduct_DOI/README_Great_Lakes_Lake_Fix.md` |
| Example commands | `NADaymet/dataProduct_DOI/command.txt` |
| Base surfdata | `NADaymet/dataProduct_DOI/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc` |
| Corrected surfdata | `NADaymet/dataProduct_DOI/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc` |
