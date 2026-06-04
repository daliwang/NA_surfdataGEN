#!/usr/bin/env python3
"""
Re-count landtype pixel totals only for na_mask cells that changed 0→1.

Full-domain class_count_na_para.py re-processes all ~21M active cells (~90 min
per class). After a regional mask fix, only newly opened cells need updating;
existing mask=1 cells keep their prior counts.

Example (Great Lakes fix, 959 cells vs na_mask.tif.bak_glfix):
  python3 recount_opened_mask_cells.py --dry-run
  python3 recount_opened_mask_cells.py
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask
from shapely.geometry import box

DEFAULT_NAD = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet"
)
DEFAULT_NA_MASK = DEFAULT_NAD / "entire_domain/na_mask.tif"
DEFAULT_NA_BAK = DEFAULT_NA_MASK.with_suffix(".tif.bak_glfix")
DEFAULT_ENT = DEFAULT_NAD / "entire_domain"


def opened_cells(na_mask: Path, na_bak: Path) -> np.ndarray:
    with rasterio.open(na_bak) as old, rasterio.open(na_mask) as new:
        old_data = old.read(1)
        new_data = new.read(1)
    return np.argwhere((old_data == 0) & (new_data == 1))


def count_class_in_cell(
    row: int,
    col: int,
    transform: rasterio.Affine,
    landtype_src: rasterio.io.DatasetReader,
    class_id: int,
) -> int:
    x_min, y_min = transform * (col, row)
    x_max, y_max = transform * (col + 1, row + 1)
    polygon = box(x_min, y_min, x_max, y_max)
    out_image, _ = rio_mask(landtype_src, [polygon], crop=True)
    return int(np.sum(out_image[0] == class_id))


def patch_class(
    class_id: int,
    opened_idx: np.ndarray,
    ent_dir: Path,
    nad_dir: Path,
    transform: rasterio.Affine,
    dry_run: bool,
) -> None:
    src_tif = next(ent_dir.glob(f"nalcms_{class_id}_*.tif"), None)
    if src_tif is None:
        raise FileNotFoundError(f"No nalcms_{class_id}_*.tif in {ent_dir}")

    out_tif = nad_dir / f"landtype{class_id}_count_in_namask.tif"
    if not out_tif.exists():
        raise FileNotFoundError(f"Missing count layer: {out_tif}")

    print(f"Class {class_id:2d}: {src_tif.name} -> {out_tif.name}")

    if dry_run:
        print(f"  would re-count {len(opened_idx)} opened cells")
        return

    with rasterio.open(src_tif) as landtype_src, rasterio.open(out_tif, "r+") as dst:
        data = dst.read(1)
        for i, (row, col) in enumerate(opened_idx):
            data[row, col] = count_class_in_cell(
                int(row), int(col), transform, landtype_src, class_id
            )
            if (i + 1) % 200 == 0:
                print(f"  counted {i + 1}/{len(opened_idx)} cells")
        dst.write(data, 1)
    print(f"  patched {len(opened_idx)} cells")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nad-root", type=Path, default=DEFAULT_NAD)
    parser.add_argument("--na-mask", type=Path, default=DEFAULT_NA_MASK)
    parser.add_argument(
        "--na-mask-bak",
        type=Path,
        default=DEFAULT_NA_BAK,
        help="Baseline mask before regional fix (default: .bak_glfix).",
    )
    parser.add_argument(
        "--classes",
        type=str,
        default="1-19",
        help='Classes to patch, e.g. "1-19" or "14,18".',
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--backup-counts",
        action="store_true",
        help="Copy landtype*_count_in_namask.tif to landtype_count_bak_opened/ first.",
    )
    args = parser.parse_args()

    if not args.na_mask_bak.exists():
        raise FileNotFoundError(f"Missing backup mask: {args.na_mask_bak}")

    ent_dir = args.nad_root / "entire_domain"
    idx = opened_cells(args.na_mask, args.na_mask_bak)
    print(f"Newly opened cells (0→1): {len(idx):,}")
    if len(idx) == 0:
        print("Nothing to patch.")
        return 0

    if "-" in args.classes:
        lo, hi = args.classes.split("-", 1)
        classes = list(range(int(lo), int(hi) + 1))
    else:
        classes = [int(x.strip()) for x in args.classes.split(",") if x.strip()]

    if args.backup_counts and not args.dry_run:
        bak_dir = args.nad_root / "landtype_count_bak_opened"
        bak_dir.mkdir(exist_ok=True)
        for c in classes:
            src = args.nad_root / f"landtype{c}_count_in_namask.tif"
            if src.exists():
                shutil.copy2(src, bak_dir / src.name)
        print(f"Backed up count layers to {bak_dir}")

    with rasterio.open(args.na_mask) as m:
        transform = m.transform

    for class_id in classes:
        patch_class(class_id, idx, ent_dir, args.nad_root, transform, args.dry_run)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
