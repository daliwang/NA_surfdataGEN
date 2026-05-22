# Great Lakes lake-landunit correction

## Root cause

NALCMS classifies open water in the **Great Lakes as class 14 (Wetland)**, not class 18 (Water).

The standard NA_surfdataGEN pipeline:

1. `nalcms_seperate_class*.py` splits NALCMS into per-class GeoTIFFs.
2. `class_count_na_para.py` counts pixels of each class on the Daymet `na_mask.tif` grid.
3. `batch_create_pft_nc.py` maps class 14 → ELM PFT 13 (wetland vegetation) and class 18 → `lake`.
4. `pft_urban_lake_glacier_percentage.py` computes `PCT_LAKE` from **class-18 counts only**.

Because Great Lakes pixels are class 14, they enter the product as wetland/vegetation. Open-lake grid cells also often had missing cropped counts (`total_count = -32767`), which appear as ocean/white in RGB maps.

Verified at Lake Michigan center (`-87°, 45°`):

| Source | Value |
|--------|-------|
| `nalcms_18_Water.tif` | 0 |
| `nalcms_14_Wetland.tif` | 14 |
| `landtype18_count_in_namask.tif` | 0 |
| `landtype14_count_in_namask.tif` | 306 |

See **`Great_Lakes_Open_Water_Report.md`** for the full diagnostic write-up.

## Fix script

`fix_great_lakes_lake_mask.py` reclassifies NALCMS class-14 pixel counts as lake **inside buffered Great Lakes polygons** (Natural Earth 10 m lakes):

```
lake_count      += wetland14_count
pft_total_count -= wetland14_count
PCT_LAKE / PCT_NATVEG / PCT_NAT_PFT / PCT_URBAN / PCT_GLACIER recomputed from counts
```

Implementation notes:

- Class-14 counts are sampled with **Daymet projected x/y** (meters), not lon/lat.
- Default **15 km polygon buffer** covers lake extremities missed by strict Natural Earth boundaries.
- Class-18 counts are used when present; remaining cropped open-water holes inside the mask receive a representative full-cell lake count.
- PFT 13 (wetland) is reduced in proportion to transferred wetland count.

### Usage

```bash
cd NADaymet/dataProduct_DOI

python3 fix_great_lakes_lake_mask.py \
  --in-file  ./surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc \
  --out-file ./surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc \
  --landtype14-tif ../landtype14_count_in_namask.tif \
  --buffer-m 15000
```

Optional arguments:

| Flag | Default | Description |
|------|---------|-------------|
| `--landtype18-tif` | `../landtype18_count_in_namask.tif` | Class-18 water count GeoTIFF |
| `--buffer-m` | `15000` | Buffer (meters) applied to Great Lakes polygons |
| `--cache-dir` | `great_lakes_cache/` | Natural Earth shapefile cache (auto-downloaded) |

### Validation (corrected file)

After applying the fix to `c260128.nc`:

| Check | Result |
|-------|--------|
| Land-unit closure | 0 failures across 21,323,964 valid land cells |
| PFT closure | 10 pre-existing edge-case failures (unchanged from base `c260128.nc`) |
| White RGB pixels inside buffered mask | 0 |

Run internal validation from the manuscript repo (or pass `--final-nc` to point at the corrected file).

## Output file

Recommended release filename:

```
surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc
```

NetCDF attributes record `great_lakes_fix`, `great_lakes_fix_buffer_m`, `great_lakes_fix_source`, and `great_lakes_fix_script`.

## Longer-term pipeline fix (optional)

To fix at source instead of post-processing:

1. When building `nalcms_18_Water.tif`, reassign class-14 pixels inside Great Lakes (or other large-lake masks) to class 18 before counting; **or**
2. Add a rule in count aggregation: `lake_count = class18_count + class14_count_in_great_lakes`.

This preserves NALCMS class integrity elsewhere while treating known misclassified open water as lake.

## Related files

| File | Description |
|------|-------------|
| `fix_great_lakes_lake_mask.py` | Correction script |
| `Great_Lakes_Open_Water_Report.md` | Full root-cause and validation report |
| `command.txt` | Example commands (includes Great Lakes fix block) |
