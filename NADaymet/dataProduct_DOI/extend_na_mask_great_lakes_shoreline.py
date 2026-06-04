#!/usr/bin/env python3
"""
Extend na_mask.tif to include Great Lakes shoreline land cells.

The strict Natural Earth lake polygon leaves fringe 1 km grid cells at mask=0
even though they are land (NALCMS classes 1–17, 19 at the cell centre). Those
cells are excluded from class_count_na_para.py and downstream surfdata.

This script sets na_mask=1 for mask=0 cells in a shoreline band around the five
Great Lakes polygons. By default the band is one 1 km cell (8-connected dilation
of the rasterized polygon). Optionally use a metric buffer instead.

Example:
  python3 extend_na_mask_great_lakes_shoreline.py --dry-run
  python3 extend_na_mask_great_lakes_shoreline.py
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from scipy import ndimage

DEFAULT_MASK = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/"
    "NADaymet/entire_domain/na_mask.tif"
)
DEFAULT_NALCMS_30M = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/"
    "NADaymet/entire_domain/nalcms2daymet_hcompressed.tif"
)
DEFAULT_GL_SHP = Path(__file__).resolve().parent / "great_lakes_cache" / "ne_10m_lakes.shp"
GREAT_LAKE_NAMES = {
    "Lake Superior",
    "Lake Michigan",
    "Lake Huron",
    "Lake Erie",
    "Lake Ontario",
}
WATER_CLASS = 18


def load_great_lakes(shp_path: Path) -> gpd.GeoDataFrame:
    gl = gpd.read_file(shp_path)
    if gl.crs is None:
        gl = gl.set_crs("EPSG:4326")
    return gl[gl["name"].isin(GREAT_LAKE_NAMES)].copy()


def shoreline_band(
    gl_gdf: gpd.GeoDataFrame,
    shape: tuple[int, int],
    transform: rasterio.Affine,
    crs,
    *,
    dilate_cells: int,
    buffer_m: float | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (strict_lake_mask, shoreline_band_mask) as uint8 arrays."""
    gl_proj = gl_gdf.to_crs(crs) if gl_gdf.crs != crs else gl_gdf
    strict = rasterize(
        [(geom, 1) for geom in gl_proj.geometry],
        out_shape=shape,
        transform=transform,
        fill=0,
        dtype=np.uint8,
    )

    if buffer_m is not None and buffer_m > 0:
        gl_buf = gl_proj.copy()
        gl_buf["geometry"] = gl_buf.geometry.buffer(buffer_m)
        band = rasterize(
            [(geom, 1) for geom in gl_buf.geometry],
            out_shape=shape,
            transform=transform,
            fill=0,
            dtype=np.uint8,
        )
        band = (band == 1) & (strict == 0)
    else:
        struct = ndimage.generate_binary_structure(2, 2)
        band = ndimage.binary_dilation(strict == 1, structure=struct, iterations=dilate_cells)
        band = band & (strict == 0)

    return strict, band.astype(np.uint8)


def gl_bbox_mask(
    gl_gdf: gpd.GeoDataFrame,
    shape: tuple[int, int],
    transform: rasterio.Affine,
    crs,
) -> np.ndarray:
    """Boolean mask of all grid cells inside the Great Lakes bounding box."""
    gl_proj = gl_gdf.to_crs(crs) if gl_gdf.crs != crs else gl_gdf
    minx, miny, maxx, maxy = gl_proj.total_bounds
    window = from_bounds(minx, miny, maxx, maxy, transform=transform)
    window = window.round_offsets().round_lengths()
    r0, c0 = int(window.row_off), int(window.col_off)
    h, w = int(window.height), int(window.width)
    out = np.zeros(shape, dtype=bool)
    out[r0 : r0 + h, c0 : c0 + w] = True
    return out


def center_class(
    rows: np.ndarray,
    cols: np.ndarray,
    transform: rasterio.Affine,
    nalcms_path: Path,
) -> np.ndarray:
    classes = np.full(len(rows), -1, dtype=np.int16)
    with rasterio.open(nalcms_path) as src:
        for i, (row, col) in enumerate(zip(rows, cols)):
            x, y = rasterio.transform.xy(transform, int(row), int(col), offset="center")
            r30, c30 = src.index(x, y)
            if 0 <= r30 < src.height and 0 <= c30 < src.width:
                classes[i] = int(src.read(1, window=((r30, r30 + 1), (c30, c30 + 1)))[0, 0])
    return classes


def write_mask(mask_path: Path, data: np.ndarray, profile: dict, backup_suffix: str) -> None:
    bak = mask_path.with_suffix(mask_path.suffix + backup_suffix)
    if mask_path.exists() and not bak.exists():
        shutil.copy2(mask_path, bak)
        print(f"Backup: {bak}")

    out_profile = profile.copy()
    out_profile.update(dtype=rasterio.uint8, nodata=255, count=1)
    with rasterio.open(mask_path, "w", **out_profile) as dst:
        dst.write(data.astype(np.uint8), 1)
    print(f"Wrote {mask_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--na-mask", type=Path, default=DEFAULT_MASK)
    parser.add_argument("--nalcms-30m", type=Path, default=DEFAULT_NALCMS_30M)
    parser.add_argument("--gl-shp", type=Path, default=DEFAULT_GL_SHP)
    parser.add_argument(
        "--dilate-cells",
        type=int,
        default=3,
        help="Shoreline band width in 1 km cells (8-connected dilation). Ignored if --buffer-m is set.",
    )
    parser.add_argument(
        "--buffer-m",
        type=float,
        default=None,
        help="Use a metric buffer around lake polygons instead of grid dilation.",
    )
    parser.add_argument(
        "--fill-bbox-remainder",
        action="store_true",
        help="Also open all remaining mask=0 land cells inside the GL bounding box.",
    )
    parser.add_argument(
        "--bbox-only",
        action="store_true",
        help="Only fill bbox remainder cells (skip shoreline dilation band).",
    )
    parser.add_argument(
        "--include-water-centers",
        action="store_true",
        help="Also open mask=0 cells whose 30 m centre is class 18.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--backup-suffix",
        default=".bak_gl_shoreline",
        help="Backup suffix before writing (default: .bak_gl_shoreline).",
    )
    args = parser.parse_args()

    gl = load_great_lakes(args.gl_shp)
    with rasterio.open(args.na_mask) as m:
        mask_data = m.read(1).astype(np.uint8)
        profile = m.profile
        transform = m.transform
        crs = m.crs

    strict, band = shoreline_band(
        gl,
        mask_data.shape,
        transform,
        crs,
        dilate_cells=args.dilate_cells,
        buffer_m=args.buffer_m,
    )

    candidates = np.zeros(mask_data.shape, dtype=bool)
    if not args.bbox_only:
        candidates |= (mask_data == 0) & (band == 1)
        print(f"Shoreline-band mask=0 candidates: {int(((mask_data == 0) & (band == 1)).sum())}")
    if args.fill_bbox_remainder or args.bbox_only:
        bbox = gl_bbox_mask(gl, mask_data.shape, transform, crs)
        bbox_remainder = (mask_data == 0) & bbox
        candidates |= bbox_remainder
        print(f"GL bbox remainder mask=0 candidates: {int(bbox_remainder.sum())}")

    idx = np.argwhere(candidates)
    print(f"Total unique candidates: {len(idx)}")

    if len(idx) == 0:
        print("Nothing to change.")
        return 0

    if not args.include_water_centers and args.nalcms_30m.exists():
        classes = center_class(idx[:, 0], idx[:, 1], transform, args.nalcms_30m)
        keep = classes != WATER_CLASS
        skipped = int((~keep).sum())
        if skipped:
            print(f"Skipping {skipped} cells with 30 m centre class {WATER_CLASS}")
        idx = idx[keep]

    print(f"Cells to open (mask 0 -> 1): {len(idx)}")
    if len(idx) == 0:
        print("Nothing to change after land filter.")
        return 0

    updated = mask_data.copy()
    updated[idx[:, 0], idx[:, 1]] = 1
    print(
        f"Updated na_mask active cells: {(updated == 1).sum()} "
        f"(+{len(idx)}; was {(mask_data == 1).sum()})"
    )

    if args.dry_run:
        print("Dry run; no files written.")
        return 0

    write_mask(args.na_mask, updated, profile, args.backup_suffix)

    root_mask = args.na_mask.parent.parent / "na_mask.tif"
    if root_mask != args.na_mask and root_mask.parent.exists():
        write_mask(root_mask, updated, profile, args.backup_suffix)

    print(
        "\nNext steps: re-run class_count_na_para.py for newly opened shoreline cells, "
        "or use prepare_open_mask_cells.py if a .bak is available."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
