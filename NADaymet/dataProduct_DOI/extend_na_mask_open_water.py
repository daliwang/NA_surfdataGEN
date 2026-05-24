#!/usr/bin/env python3
"""
Extend na_mask.tif to include inland open-water (NALCMS class 18) 1 km cells.

Open-lake grid cells are currently na_mask=0, so class_count_na_para.py never
aggregates class-18 pixels inside them and landtype18_count_in_namask.tif stays
-1.  The 30 m source (nalcms2daymet_hcompressed.tif) maps Great Lakes and other
inland open water as class 18.

This script sets na_mask=1 for cells that are currently mask=0 and whose 30 m
source class at the 1 km cell centre is 18 (Water).  Optional blockwise zonal
mode requires a minimum class-18 fraction inside each cell.

After updating the mask, use --update-landtype18 to patch
landtype18_count_in_namask.tif for newly opened cells only (fast), or re-run
class_count_na_para.py for a full rebuild.

Example:
  python3 extend_na_mask_open_water.py --dry-run
  python3 extend_na_mask_open_water.py --update-landtype18
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from shapely.geometry import box
from rasterio.mask import mask as rio_mask

DEFAULT_MASK = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/"
    "NADaymet/entire_domain/na_mask.tif"
)
DEFAULT_NALCMS_30M = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/"
    "NADaymet/entire_domain/nalcms2daymet_hcompressed.tif"
)
DEFAULT_LANDTYPE18 = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/"
    "NADaymet/landtype18_count_in_namask.tif"
)
WATER_CLASS = 18
BATCH_SIZE = 200_000


def _sample_centers_class18(
    zero_idx: np.ndarray,
    mask_transform: rasterio.Affine,
    src_path: Path,
) -> np.ndarray:
    """Return boolean mask (len zero_idx) where 30 m centre pixel is class 18."""
    is_water = np.zeros(len(zero_idx), dtype=bool)
    with rasterio.open(src_path) as src:
        for start in range(0, len(zero_idx), BATCH_SIZE):
            sl = zero_idx[start : start + BATCH_SIZE]
            rows, cols = sl[:, 0], sl[:, 1]
            xs, ys = rasterio.transform.xy(mask_transform, rows, cols, offset="center")
            r30, c30 = rasterio.transform.rowcol(src.transform, xs, ys)
            r30 = np.asarray(r30, dtype=np.int64)
            c30 = np.asarray(c30, dtype=np.int64)
            ok = (r30 >= 0) & (r30 < src.height) & (c30 >= 0) & (c30 < src.width)
            if not np.any(ok):
                continue
            r0, r1 = int(r30[ok].min()), int(r30[ok].max()) + 1
            c0, c1 = int(c30[ok].min()), int(c30[ok].max()) + 1
            win = Window(c0, r0, c1 - c0, r1 - r0)
            data = src.read(1, window=win)
            vals = data[r30[ok] - r0, c30[ok] - c0]
            local = np.zeros(len(sl), dtype=bool)
            local[ok] = vals == WATER_CLASS
            is_water[start : start + len(sl)] = local
    return is_water


def _zonal_class18_fraction(
    zero_idx: np.ndarray,
    mask_transform: rasterio.Affine,
    src_path: Path,
    min_fraction: float,
    block_size: int = 128,
) -> np.ndarray:
    """Blockwise zonal fraction of class 18 inside each 1 km cell."""
    is_water = np.zeros(len(zero_idx), dtype=bool)
    rc_to_pos = {(int(r), int(c)): i for i, (r, c) in enumerate(zero_idx)}

    with rasterio.open(src_path) as src:
        max_row = int(zero_idx[:, 0].max()) + 1
        max_col = int(zero_idx[:, 1].max()) + 1
        for r0 in range(0, max_row, block_size):
            r1 = min(r0 + block_size, max_row)
            for c0 in range(0, max_col, block_size):
                c1 = min(c0 + block_size, max_col)
                block_cells = [
                    (r, c)
                    for r in range(r0, r1)
                    for c in range(c0, c1)
                    if (r, c) in rc_to_pos
                ]
                if not block_cells:
                    continue

                x_min, y_max = mask_transform * (c0, r0)
                x_max, y_min = mask_transform * (c1, r1)
                poly = box(x_min, y_min, x_max, y_max)
                out, out_tr = rio_mask(src, [poly], crop=True)
                arr = out[0]

                for r, c in block_cells:
                    cx_min, y_min = mask_transform * (c, r)
                    cx_max, y_max = mask_transform * (c + 1, r + 1)
                    col_a, row_a = rasterio.transform.rowcol(out_tr, cx_min, y_min)
                    col_b, row_b = rasterio.transform.rowcol(out_tr, cx_max, y_max)
                    row_lo, row_hi = sorted((row_a, row_b))
                    col_lo, col_hi = sorted((col_a, col_b))
                    row_lo = max(0, int(row_lo))
                    row_hi = min(arr.shape[0], int(row_hi) + 1)
                    col_lo = max(0, int(col_lo))
                    col_hi = min(arr.shape[1], int(col_hi) + 1)
                    if row_lo >= row_hi or col_lo >= col_hi:
                        continue
                    sub = arr[row_lo:row_hi, col_lo:col_hi]
                    valid = sub != src.nodata if src.nodata is not None else np.ones(sub.shape, bool)
                    n_valid = int(valid.sum())
                    if n_valid == 0:
                        continue
                    frac = float((sub[valid] == WATER_CLASS).sum()) / n_valid
                    if frac >= min_fraction:
                        is_water[rc_to_pos[(r, c)]] = True
    return is_water


def _class18_count_in_cell(
    row: int,
    col: int,
    mask_transform: rasterio.Affine,
    src: rasterio.io.DatasetReader,
) -> int:
    """Count class-18 pixels in one 1 km cell (matches class_count_na_para.py)."""
    x_min, y_min = mask_transform * (col, row)
    x_max, y_max = mask_transform * (col + 1, row + 1)
    polygon = box(x_min, y_min, x_max, y_max)
    out_image, _ = rio_mask(src, [polygon], crop=True)
    return int(np.sum(out_image[0] == WATER_CLASS))


def patch_landtype18_counts(
    new_cells: np.ndarray,
    mask_path: Path,
    landtype18_path: Path,
    nalcms_30m: Path,
    block_size: int = 128,
) -> None:
    if new_cells.size == 0:
        print("No new mask cells; skipping landtype18 patch.")
        return

    with rasterio.open(landtype18_path, "r+") as dst, rasterio.open(mask_path) as m, rasterio.open(
        nalcms_30m
    ) as src:
        data = dst.read(1)
        tr = m.transform
        n_cells = len(new_cells)
        print(f"Patching {n_cells} cells in {landtype18_path.name} ...")

        for i, (row, col) in enumerate(new_cells):
            data[row, col] = _class18_count_in_cell(int(row), int(col), tr, src)
            if (i + 1) % 5000 == 0:
                print(f"  counted {i + 1}/{n_cells} cells")

        dst.write(data, 1)
    print(f"Updated {landtype18_path} ({n_cells} cells)")


def write_mask(mask_path: Path, data: np.ndarray, profile: dict, backup: bool) -> None:
    if backup and mask_path.exists():
        bak = mask_path.with_suffix(mask_path.suffix + ".bak")
        if not bak.exists():
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
    parser.add_argument("--landtype18-tif", type=Path, default=DEFAULT_LANDTYPE18)
    parser.add_argument(
        "--method",
        choices=("center", "zonal"),
        default="center",
        help="center: 30 m class at 1 km cell centre (fast). zonal: min fraction in cell.",
    )
    parser.add_argument(
        "--min-fraction",
        type=float,
        default=0.5,
        help="Minimum class-18 fraction for --method zonal (default 0.5).",
    )
    parser.add_argument(
        "--update-landtype18",
        action="store_true",
        help="Patch landtype18_count_in_namask.tif for newly opened cells.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write.")
    parser.add_argument(
        "--patch-only",
        action="store_true",
        help="Skip mask update; patch landtype18 for cells opened in na_mask vs .bak.",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="With --patch-only, skip cells that already have landtype18 count > 0.",
    )
    args = parser.parse_args()

    if args.patch_only:
        bak = args.na_mask.with_suffix(args.na_mask.suffix + ".bak")
        if not bak.exists():
            raise FileNotFoundError(f"Missing backup mask for --patch-only: {bak}")
        with rasterio.open(bak) as old, rasterio.open(args.na_mask) as new:
            old_data = old.read(1)
            new_data = new.read(1)
        new_cells = np.argwhere((old_data == 0) & (new_data == 1))
        if args.only_missing and args.landtype18_tif.exists():
            with rasterio.open(args.landtype18_tif) as t:
                counts = t.read(1)
            keep = counts[new_cells[:, 0], new_cells[:, 1]] <= 0
            new_cells = new_cells[keep]
        print(f"--patch-only: {len(new_cells)} cells to patch")
        patch_landtype18_counts(new_cells, args.na_mask, args.landtype18_tif, args.nalcms_30m)
        return 0

    with rasterio.open(args.na_mask) as m:
        mask_data = m.read(1).astype(np.uint8)
        profile = m.profile
        transform = m.transform

    zero_idx = np.argwhere(mask_data == 0)
    print(f"Current na_mask: {(mask_data == 1).sum()} active, {(mask_data == 0).sum()} inactive")

    if args.method == "center":
        print(f"Finding open-water cells (30 m centre class {WATER_CLASS}) ...")
        open_water = _sample_centers_class18(zero_idx, transform, args.nalcms_30m)
    else:
        print(f"Finding open-water cells (zonal fraction >= {args.min_fraction}) ...")
        open_water = _zonal_class18_fraction(
            zero_idx, transform, args.nalcms_30m, args.min_fraction
        )

    new_cells = zero_idx[open_water]
    print(f"Cells to open (mask 0 -> 1): {len(new_cells)}")

    if len(new_cells) == 0:
        print("Nothing to change.")
        return 0

    updated = mask_data.copy()
    updated[new_cells[:, 0], new_cells[:, 1]] = 1
    print(f"Updated na_mask active cells: {(updated == 1).sum()} (+{len(new_cells)})")

    if args.dry_run:
        print("Dry run; no files written.")
        return 0

    write_mask(args.na_mask, updated, profile, backup=not args.no_backup)

    root_mask = args.na_mask.parent.parent / "na_mask.tif"
    if root_mask != args.na_mask and root_mask.parent.exists():
        write_mask(root_mask, updated, profile, backup=not args.no_backup)

    if args.update_landtype18:
        if not args.landtype18_tif.exists():
            raise FileNotFoundError(
                f"{args.landtype18_tif} not found; run class_count_na_para.py first "
                "or omit --update-landtype18."
            )
        patch_landtype18_counts(new_cells, args.na_mask, args.landtype18_tif, args.nalcms_30m)

    print(
        "\nNext steps: re-run class_count_na_para.py for all land-cover classes "
        "(or at least class 18 if not using --update-landtype18), then rebuild "
        "combined PFT / surfdata products.  Also apply the pft_total_count -1 fix "
        "in pft_total_count_percentage.py for water-dominated cells already inside na_mask."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
