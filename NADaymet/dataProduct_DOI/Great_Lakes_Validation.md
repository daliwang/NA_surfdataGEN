# Great Lakes Region Validation

This note tracks the Great Lakes validation checks and plots for the NA surfdata rebuild.

## Goals
- Ensure the NA mask includes all Great Lakes cells (mask=1).
- Verify the 30 m reprojected NALCMS map contains only classes 1–19 (no invalid codes).
- Verify the Daymet temperature alignment to the large NALCMS mask (dy=72 vs dy=100).
- Provide zoomed plots around the Great Lakes for review.

## Summary Results (2026-06-03)
### NA mask coverage (Great Lakes polygon)
- Mask file: `NADaymet/entire_domain/na_mask.tif`
- GL mask cells: **223,195**
- mask=1 inside GL polygon: **223,195** (601 open-lake cells flipped 2026-06-03)
- Shoreline fringe (3-cell band outside polygon): **324** land cells flipped to mask=1 (2026-06-03; 247 at 1-cell + 77 at 3-cell)
- GL bbox remainder: **34** land cells flipped to mask=1 (2026-06-03)
- mask=0 remaining in GL zoom bbox: **0**

### GL zoom panel validation (2026-06-03) — **PASS**
- Window: Great Lakes polygon bounding box, shape **768 × 1239** (951,552 cells)
- Checked files: `NADaymet/entire_domain/na_mask.tif`, `NADaymet/na_mask.tif`
- Result: **mask=1 = 951,552**, **mask=0 = 0**, unique values = `[1]` only
- Plot check: `figures_c260603_na_mask_full_vs_gl_zoom.png` (right panel fully active / white)

## Baseline mask for recount (2026-06-03)

**Authoritative mask:** `NADaymet/entire_domain/na_mask.tif` (mirrored to `NADaymet/na_mask.tif`)

This is the mask to use when re-counting:

| Layer | Scripts (in order) |
|-------|-------------------|
| **Landtype 1–19 pixel counts** | `class_count_na_para.py` → `landtype{N}_count_in_namask.tif` |
| **Landtype NetCDFs** | `landtypes_count/landtype_tif2nc.py` |
| **Individual PFT counts + %** | `ELM_PFTs/combine_pft_counts.py` → `pft_total_count_percentage.py` |
| **Lake / urban / glacier counts** | `ELM_PFTs/lake_*.py`, `urban_*.py`, `glacier_*.py` (from landtype 17–19 NC) |
| **Combined totals + %** | `pft_urban_lake_glacier_percentage.py` → `make_land_veg_urban_lake_glacier_percentage.py` |

Full 5-phase procedure: `REPORT_Surfdata_Rebuild_5_Phase_Runbook.md`.

**GL-specific mask changes** (vs `na_mask.tif.bak_glfix`, cumulative **959** cells opened):

| Step | Cells 0→1 | Notes |
|------|-----------|--------|
| Open lake (inside polygon) | 601 | 30 m centre class 18 |
| Shoreline 1-cell band | 247 | land fringe |
| Shoreline 3-cell band | +77 | land fringe |
| GL bbox remainder | +34 | land fringe |
| **GL subtotal** | **959** | all land or lake; full class 1–19 re-count required |

**Domain-wide** (vs `na_mask.tif.bak`): **229,128** cells opened (includes earlier open-water extension).

For the **959 GL cells**, use **`recount_opened_mask_cells.py`** (patches only cells that changed 0→1 vs `na_mask.tif.bak_glfix`). Full-domain `class_count_na_para.py` is **not** required unless the baseline is `na_mask.tif.bak` (229k cells domain-wide).

```bash
python3 recount_opened_mask_cells.py --dry-run
python3 recount_opened_mask_cells.py --backup-counts
```

**Phase 1b–1c (2026-06-03):** refreshed NetCDF layers from updated GeoTIFFs (~26s + ~40s):
- Symlinked `NADaymet/landtype{1-19}_count_in_namask.tif` → `landtypes_count/`
- Regenerated `landtypes_count/landtype{N}_nalcms_*_in_daymet.nc`
- Regenerated `ELM_PFTs/ELM_PFT_output/*_landtype*.nc` via `batch_create_pft_nc.py`
- NC backups: `landtypes_count/nc_bak_c260603/`

**Phase 2 (2026-06-03):** PFT + land-unit combine (~88s):
- `ELM_PFT_output/combined_pft_count.nc`
- `ELM_PFT_output/pft_total_count_percentage.nc` (per-PFT counts + percentages)
- `ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.nc`
- `dataProduct_DOI/land_veg_urban_lake_glacier_percentage.nc`
- Backups: `ELM_PFT_output/phase2_bak_c260603/`

**Phase 3–4 (2026-06-03):** crop + final surfdata (~6 min):
- Cropped layers (dx=98, dy=72): `land_veg_urban_lake_glacier_percentage.cropped_to_surfdata.nc`, `pft_total_count_percentage.cropped_to_surfdata.nc`, `combined_pft_urban_lake_glacier_total_count.cropped_to_surfdata.nc`
- **Final product:** `surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260603.nc`
- GL diagnostic: **0** fill cells (missing `PCT_LAKE`) in Great Lakes bbox
- Plot: `figures_c260603_surfdata_pct_lake_full_vs_gl_zoom.png`
- Backups: `dataProduct_DOI/phase34_bak_c260603/`

### NALCMS 30 m class validity (Great Lakes polygon)
- Source: `NADaymet/NALCMS2DAYMET_30m_max.tif`
- GL pixels: **248,014,552**
- NODATA (127): **0**
- Invalid (non 1–19, excluding NODATA): **0**

## Temperature Alignment Notes
- Daymet temp (`mean_temperature_coldest_month.nc`) has **y increasing south→north**.
- Large NALCMS mask grid has **y decreasing north→south**.
- Therefore Daymet must be **flipped in y** before alignment.
- Offsets determined from coordinate ranges:
  - **dx=98, dy=100** aligns Daymet to the large mask grid.
  - **dx=98, dy=72** is used for **cropping to surfdata** (not temp alignment).

## Plots (Great Lakes Zoom)
### NA mask and class validity
- NA mask zoom: `figures_c260603_gl_na_mask_zoom.png`
- NALCMS invalid-class mask: `figures_c260603_gl_nalcms_invalid_classes.png`

### Daymet temp alignment (Great Lakes zoom)
- dy=100 alignment: `figures_c260603_gl_temp_aligned_dy100.png`
- dy=72 alignment: `figures_c260603_gl_temp_aligned_dy72.png`

### Great Lakes partial-cell plots
- `figures_c260128_great_lakes_partial_cells.png`
- `figures_c260524_great_lakes_partial_cells.png`
- `figures_c260605_great_lakes_partial_cells.png`

## Repro Commands (reference)
```
# Validate GL zoom is fully active (all mask=1)
python3 - <<'PY'
import numpy as np, rasterio, geopandas as gpd
from rasterio.windows import from_bounds
from pathlib import Path

root = Path('NADaymet')
mask_path = root / 'entire_domain/na_mask.tif'
shp = root / 'dataProduct_DOI/great_lakes_cache/ne_10m_lakes.shp'
GL_NAMES = {"Lake Superior", "Lake Michigan", "Lake Huron", "Lake Erie", "Lake Ontario"}
gl = gpd.read_file(shp)
if gl.crs is None: gl = gl.set_crs('EPSG:4326')
gl = gl[gl['name'].isin(GL_NAMES)]

with rasterio.open(mask_path) as msk:
    gl_proj = gl.to_crs(msk.crs)
    minx, miny, maxx, maxy = gl_proj.total_bounds
    w = from_bounds(minx, miny, maxx, maxy, transform=msk.transform).round_offsets().round_lengths()
    zoom = msk.read(1, window=w, boundless=True, fill_value=0)

assert (zoom == 1).all(), f"FAIL: {(zoom==0).sum()} mask=0 cells remain"
print(f"PASS: GL zoom {zoom.shape} all mask=1 ({zoom.size} cells)")
PY

# NA mask / NALCMS GL stats + zoom plots
python3 - <<'PY'
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point

mask_path = Path('NADaymet/entire_domain/na_mask.tif')
nalcms_path = Path('NADaymet/NALCMS2DAYMET_30m_max.tif')
shp = Path('NADaymet/dataProduct_DOI/great_lakes_cache/ne_10m_lakes.shp')
GL_NAMES = {"Lake Superior", "Lake Michigan", "Lake Huron", "Lake Erie", "Lake Ontario"}
gl = gpd.read_file(shp)
if gl.crs is None:
    gl = gl.set_crs('EPSG:4326')
gl = gl[gl['name'].isin(GL_NAMES)].copy()
PY

# Temp alignment plots (dy=100/dy=72)
python3 - <<'PY'
from netCDF4 import Dataset
import matplotlib.pyplot as plt
for label, path, out in [
    ('dy100','NADaymet/ELM_PFTs/aligned_temp_to_large_nalcms_mask_from_daymet.nc',
     'NADaymet/dataProduct_DOI/figures_c260603_gl_temp_aligned_dy100.png'),
    ('dy72','NADaymet/ELM_PFTs/aligned_temp_to_large_nalcms_mask_from_daymet_dy72.nc',
     'NADaymet/dataProduct_DOI/figures_c260603_gl_temp_aligned_dy72.png'),
]:
    with Dataset(path) as nc:
        temp = nc.variables['AvgTemp'][:]
    plt.figure(figsize=(6,6))
    plt.imshow(temp, origin='upper', cmap='coolwarm')
    plt.title(label)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(out, dpi=220)
    plt.close()
PY
```
