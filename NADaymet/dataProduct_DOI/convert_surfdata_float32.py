#!/usr/bin/env python3
"""
Convert a Surfdata NetCDF to:
  - float64 → float32 for all float variables (including coords)
  - rename dims: lon→x, lat→y
  - compress variables with zlib, complevel=5 (configurable)

Example:
  python3 NA_surfdataGEN/NADaymet/dataProduct_DOI/convert_surfdata_float32.py \
    --in  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_and_temp.nc \
    --out /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/NA_surfdata_nalcms2daymet_pft_landunit_temp.nc \
    --level 5
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List

try:
    import xarray as xr
    import numpy as np
except Exception:
    print("ERROR: Requires xarray and numpy. Install with: pip install xarray netCDF4 h5netcdf numpy", file=sys.stderr)
    raise


def try_open(path: str) -> xr.Dataset:
    errors: List[str] = []
    for eng in ("netcdf4", "h5netcdf", "scipy", None):
        try:
            ds = xr.open_dataset(path, engine=eng)
            _ = list(ds.dims.items())
            return ds
        except Exception as exc:
            errors.append(f"{eng}: {exc}")
    raise RuntimeError(f"Failed to open {path}:\n" + "\n".join(errors))


def main() -> None:
    p = argparse.ArgumentParser(description="Convert Surfdata NetCDF to float32, rename dims, and compress.")
    p.add_argument("--in", dest="in_path", required=True, help="Input NetCDF path")
    p.add_argument("--out", dest="out_path", required=True, help="Output NetCDF path")
    p.add_argument("--level", type=int, default=5, help="Compression level (0-9), default 5")
    args = p.parse_args()

    ds = try_open(args.in_path)

    # Rename dims lon→x, lat→y (if present)
    rename_dims: Dict[str, str] = {}
    if "lon" in ds.dims:
        rename_dims["lon"] = "x"
    if "lat" in ds.dims:
        rename_dims["lat"] = "y"
    if rename_dims:
        ds = ds.rename(rename_dims)

    # Also ensure coordinate variables carry the new dims.
    # Keep variable names 'lat'/'lon' unchanged unless user wants otherwise.
    # But if they exist, cast to float32 to satisfy "double → float".
    cast_vars: Dict[str, xr.DataArray] = {}
    for name, da in {**ds.data_vars, **ds.coords}.items():
        if np.issubdtype(da.dtype, np.floating) and da.dtype == np.float64:
            cast_vars[name] = da.astype(np.float32)
    if cast_vars:
        ds = ds.assign({k: v for k, v in cast_vars.items()})

    # Build encoding with compression for all data variables and coords
    encoding: Dict[str, Dict] = {}
    for name, da in {**ds.data_vars, **ds.coords}.items():
        # Only set dtype for float arrays to float32, others keep default
        enc: Dict = {"zlib": True, "complevel": args.level}
        if np.issubdtype(da.dtype, np.floating):
            enc["dtype"] = "float32"
        encoding[name] = enc

    os.makedirs(os.path.dirname(args.out_path), exist_ok=True)
    ds.to_netcdf(args.out_path, encoding=encoding)
    print(f"Wrote converted file: {args.out_path}")


if __name__ == "__main__":
    main()


