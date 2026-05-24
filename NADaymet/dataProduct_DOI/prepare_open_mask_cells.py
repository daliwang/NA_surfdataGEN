#!/usr/bin/env python3
"""
Prepare count layers after na_mask open-water extension (minimal path, no full 1–19 re-count).

1. Set landtype{1-17,19}_count_in_namask.tif from -1 to 0 on newly opened cells (mask 0→1).
2. Write landtype18 GeoTIFF → landtypes_count/landtype18_nalcms_Water_in_daymet.nc.
3. Rebuild ELM_PFT_output/lake_landtype18_nalcms_Water_in_daymet.nc.
4. Zero urban_count / glacier_count on new cells in existing ELM_PFT_output NetCDFs.

Sanity check (2026-05-24): 228,169 new cells are 100% class-18 water at 30 m centre;
full re-count of classes 1–17 and 19 is not required.

Example:
  python3 prepare_open_mask_cells.py --dry-run
  python3 prepare_open_mask_cells.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from netCDF4 import Dataset

DEFAULT_REPO = Path("/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet")
SENTINEL_CLASSES = list(range(1, 18)) + [19]
LAKE_CLASS = 18


def new_mask_cells(na_mask: Path, na_mask_bak: Path) -> np.ndarray:
    with rasterio.open(na_mask_bak) as old, rasterio.open(na_mask) as new:
        return (old.read(1) == 0) & (new.read(1) == 1)


def patch_sentinel_tifs(
    nad: Path,
    opened: np.ndarray,
    classes: list[int],
    dry_run: bool,
) -> dict[int, int]:
    """Set -1 → 0 on newly opened cells for non-water class count GeoTIFFs."""
    stats: dict[int, int] = {}
    for c in classes:
        tif = nad / f"landtype{c}_count_in_namask.tif"
        if not tif.exists():
            print(f"  skip class {c}: {tif.name} not found")
            continue
        with rasterio.open(tif, "r+") as dst:
            data = dst.read(1)
            sub = data[opened]
            n_patch = int((sub == -1).sum())
            stats[c] = n_patch
            if dry_run:
                print(f"  class {c:2d}: would patch {n_patch:,} cells (-1 → 0)")
                continue
            if n_patch:
                data[opened & (data == -1)] = 0
                dst.write(data, 1)
                print(f"  class {c:2d}: patched {n_patch:,} cells (-1 → 0)")
            else:
                print(f"  class {c:2d}: nothing to patch")
    return stats


def write_landtype18_nc(nad: Path, landtypes_count: Path, dry_run: bool) -> Path:
    """GeoTIFF → landtypes_count/landtype18_nalcms_Water_in_daymet.nc."""
    tif = nad / "landtype18_count_in_namask.tif"
    nc_out = landtypes_count / "landtype18_nalcms_Water_in_daymet.nc"
    with rasterio.open(tif) as src:
        data = src.read(1).astype(np.float32)
        data[data < 0] = np.nan
        shape = data.shape

    if dry_run:
        print(f"  would write {nc_out} from {tif.name} shape={shape}")
        return nc_out

    with Dataset(nc_out, "w", format="NETCDF4") as nc:
        nc.createDimension("y", shape[0])
        nc.createDimension("x", shape[1])
        var = nc.createVariable("landtype_count", "f4", ("y", "x"), fill_value=np.nan, zlib=True, complevel=5)
        var[:, :] = data
        var.units = "count"
        var.long_name = "Landtype 18 (Water) count per gridcell"
        nc.description = f"From {tif.name} after na_mask open-water extension"
    print(f"  wrote {nc_out}")
    return nc_out


def rebuild_lake_pft_nc(landtypes_count: Path, pft_out: Path, dry_run: bool) -> Path:
    """landtypes_count NC → ELM_PFT_output/lake_landtype18_*.nc."""
    src_nc = landtypes_count / "landtype18_nalcms_Water_in_daymet.nc"
    out_nc = pft_out / "lake_landtype18_nalcms_Water_in_daymet.nc"
    with Dataset(src_nc) as src:
        count = src.variables["landtype_count"][:]
    count_i = np.nan_to_num(count, nan=0.0).astype(np.int32)
    count_i[count < 0] = 0

    if dry_run:
        print(f"  would write {out_nc} lake_count max={count_i.max()}")
        return out_nc

    pft_out.mkdir(parents=True, exist_ok=True)
    with Dataset(out_nc, "w", format="NETCDF4") as dst:
        ny, nx = count_i.shape
        dst.createDimension("y", ny)
        dst.createDimension("x", nx)
        var = dst.createVariable("lake_count", "i4", ("y", "x"), zlib=True, complevel=5)
        var[:, :] = count_i
        var.long_name = "lake count based on landtype18_nalcms_Water_in_daymet.nc"
        var.units = "count"
        dst.setncattr("original_landtype_file", "landtype18_nalcms_Water_in_daymet.nc")
    print(f"  wrote {out_nc}")
    return out_nc


def zero_new_cells_in_nc(
    nc_path: Path,
    var_name: str,
    opened: np.ndarray,
    dry_run: bool,
) -> int:
    if not nc_path.exists():
        print(f"  skip {nc_path.name}: not found")
        return 0
    with Dataset(nc_path, "r+") as nc:
        arr = nc.variables[var_name][:]
        # support (y,x) or (file,y,x)
        if arr.ndim == 3:
            target = arr[0]
            n = int((opened & (target != 0)).sum())
            if dry_run:
                print(f"  {nc_path.name}:{var_name} would zero {n:,} non-zero new cells")
                return n
            arr[0][opened] = 0
            nc.variables[var_name][:] = arr
        else:
            n = int((opened & (arr != 0)).sum())
            if dry_run:
                print(f"  {nc_path.name}:{var_name} would zero {n:,} non-zero new cells")
                return n
            arr[opened] = 0
            nc.variables[var_name][:] = arr
    print(f"  {nc_path.name}:{var_name} zeroed on {int(opened.sum()):,} new cells")
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nad-root", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    nad = args.nad_root
    ent = nad / "entire_domain"
    landtypes_count = nad / "landtypes_count"
    pft_out = nad / "ELM_PFTs" / "ELM_PFT_output"
    na_mask = ent / "na_mask.tif"
    na_bak = ent / "na_mask.tif.bak"

    if not na_bak.exists():
        raise FileNotFoundError(f"Missing {na_bak}; cannot identify newly opened cells.")

    opened = new_mask_cells(na_mask, na_bak)
    n_open = int(opened.sum())
    print(f"Newly opened cells (na_mask 0→1): {n_open:,}")

    print("\n[1/4] Patch sentinel -1 → 0 on non-water class GeoTIFFs")
    patch_sentinel_tifs(nad, opened, SENTINEL_CLASSES, args.dry_run)

    print("\n[2/4] Write landtype18 count NetCDF")
    write_landtype18_nc(nad, landtypes_count, args.dry_run)

    print("\n[3/4] Rebuild lake PFT-layer NetCDF")
    rebuild_lake_pft_nc(landtypes_count, pft_out, args.dry_run)

    print("\n[4/4] Zero urban / glacier counts on new cells in ELM_PFT_output")
    zero_new_cells_in_nc(pft_out / "urban_landtype17_nalcms_Urban_in_daymet.nc", "urban_count", opened, args.dry_run)
    zero_new_cells_in_nc(pft_out / "glacier_landtype19_nalcms_Snow_Ice_in_daymet.nc", "glacier_count", opened, args.dry_run)

    if args.dry_run:
        print("\nDry run complete.")
    else:
        print("\nDone. Next: Phase 2 PFT combine (combine_pft_counts.py → pft_urban_lake_glacier_percentage.py).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
