#!/usr/bin/env python3
"""
Recount selected landtype classes in Great Lakes cells and fill NODATA with lake.

Strategy:
- Use NALCMS2DAYMET_30m_max.tif (30 m) for class counts.
- For Great Lakes cells only, set NODATA (127) to class 18 (Water).
- Recount classes (default: all NALCMS classes 1–19) within the 1 km cell window.
- Write updated landtype*_count_in_namask_glfix.tif outputs.

This does NOT rewrite the original count rasters unless you replace them manually.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np
import rasterio
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.prepared import prep

try:
    import geopandas as gpd
except Exception as exc:
    raise SystemExit(f"geopandas is required: {exc}")


DEFAULT_NAD = Path("/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet")
# All NALCMS land-cover classes used by landtype*_count_in_namask.tif (see prepare_open_mask_cells.py).
DEFAULT_CLASSES = tuple(range(1, 20))
GREAT_LAKE_NAMES = (
    "Lake Superior",
    "Lake Michigan",
    "Lake Huron",
    "Lake Erie",
    "Lake Ontario",
)


def load_great_lakes_union(shp_path: Path, target_crs) -> object:
    lakes = gpd.read_file(shp_path)
    gl = lakes[lakes["name"].isin(GREAT_LAKE_NAMES)].copy()
    if gl.empty:
        raise RuntimeError(f"No Great Lakes features found in {shp_path}")
    if gl.crs is None:
        gl = gl.set_crs("EPSG:4326")
    if target_crs is not None:
        gl = gl.to_crs(target_crs)
    return unary_union(gl.geometry.values)


def cell_center(transform, row: int, col: int) -> Tuple[float, float]:
    x, y = transform * (col + 0.5, row + 0.5)
    return float(x), float(y)


def bounds_for_cell(transform, row: int, col: int) -> Tuple[float, float, float, float]:
    x_min, y_min = transform * (col, row)
    x_max, y_max = transform * (col + 1, row + 1)
    left = min(x_min, x_max)
    right = max(x_min, x_max)
    bottom = min(y_min, y_max)
    top = max(y_min, y_max)
    return (left, bottom, right, top)


def main() -> None:
    p = argparse.ArgumentParser(description="Recount Great Lakes nodata pixels as water (class 18).")
    p.add_argument("--nad-root", type=Path, default=DEFAULT_NAD)
    p.add_argument(
        "--classes",
        nargs="+",
        type=int,
        default=list(DEFAULT_CLASSES),
        metavar="CLASS",
        help="NALCMS class IDs to recount (default: 1–19). Example: --classes 5 6 8 18",
    )
    p.add_argument("--nodata", type=int, default=127)
    p.add_argument("--max-cells", type=int, default=None, help="Optional cap on number of cells to process")
    args = p.parse_args()

    nad = args.nad_root
    landtype_dir = nad
    landtypes_count_dir = nad / "landtypes_count"
    gl_shp = nad / "dataProduct_DOI" / "great_lakes_cache" / "ne_10m_lakes.shp"
    base_count = landtype_dir / "landtype18_count_in_namask.tif"
    source_30m = nad / "NALCMS2DAYMET_30m_max.tif"

    if not base_count.exists():
        raise FileNotFoundError(f"Missing {base_count}")
    if not source_30m.exists():
        raise FileNotFoundError(f"Missing {source_30m}")
    if not gl_shp.exists():
        raise FileNotFoundError(f"Missing {gl_shp}")

    with rasterio.open(base_count) as src:
        count18 = src.read(1)
        transform = src.transform
        crs = src.crs
        meta = src.meta.copy()

    gl_union = load_great_lakes_union(gl_shp, crs)

    minx, miny, maxx, maxy = gl_union.bounds
    # Reduce search to bbox window in row/col space
    ul_row, ul_col = rasterio.transform.rowcol(transform, minx, maxy)
    lr_row, lr_col = rasterio.transform.rowcol(transform, maxx, miny)
    row0, row1 = sorted((ul_row, lr_row))
    col0, col1 = sorted((ul_col, lr_col))
    row0 = max(row0, 0)
    col0 = max(col0, 0)
    row1 = min(row1, count18.shape[0] - 1)
    col1 = min(col1, count18.shape[1] - 1)

    sub = count18[row0:row1 + 1, col0:col1 + 1]
    candidate = (sub > 0) & (sub < 1156)
    rows, cols = np.where(candidate)
    rows = rows + row0
    cols = cols + col0
    print(f"Candidate cells in GL bbox (count18 < 1156): {len(rows):,}", flush=True)

    a, b, c, d, e, f = transform.a, transform.b, transform.c, transform.d, transform.e, transform.f
    xs = a * (cols + 0.5) + b * (rows + 0.5) + c
    ys = d * (cols + 0.5) + e * (rows + 0.5) + f

    if args.max_cells:
        rows = rows[: args.max_cells]
        cols = cols[: args.max_cells]
        xs = xs[: args.max_cells]
        ys = ys[: args.max_cells]

    # Filter to Great Lakes polygons
    prepared = prep(gl_union)
    gl_mask = np.array([prepared.contains(Point(x, y)) for x, y in zip(xs, ys)], dtype=bool)
    rows = rows[gl_mask]
    cols = cols[gl_mask]
    print(f"Great Lakes candidate cells: {len(rows):,}", flush=True)

    if len(rows) == 0:
        print("No Great Lakes cells to process.")
        return

    # Prepare output arrays
    out_counts = {}
    for cls in args.classes:
        tif = landtype_dir / f"landtype{cls}_count_in_namask.tif"
        if not tif.exists():
            raise FileNotFoundError(f"Missing {tif}")
        with rasterio.open(tif) as src:
            out_counts[cls] = src.read(1).astype(np.int32)

    with rasterio.open(source_30m) as src30:
        nodata = src30.nodata if src30.nodata is not None else args.nodata
        for idx, (r, c) in enumerate(zip(rows, cols), 1):
            bounds = bounds_for_cell(transform, int(r), int(c))
            window = rasterio.windows.from_bounds(*bounds, transform=src30.transform)
            window = window.round_offsets().round_lengths()
            data = src30.read(1, window=window, boundless=True, fill_value=nodata)
            # Fill NODATA with lake
            data = np.where(data == nodata, 18, data)
            for cls in args.classes:
                out_counts[cls][r, c] = int(np.count_nonzero(data == cls))
            if idx % 2000 == 0:
                print(f"  processed {idx:,} cells", flush=True)

    # Write outputs
    for cls, arr in out_counts.items():
        out_path = landtype_dir / f"landtype{cls}_count_in_namask_glfix.tif"
        meta_out = meta.copy()
        meta_out.update(dtype="int32", nodata=-1)
        with rasterio.open(out_path, "w", **meta_out) as dst:
            dst.write(arr.astype(np.int32), 1)
        print(f"Wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
