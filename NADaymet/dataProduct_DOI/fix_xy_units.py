#!/usr/bin/env python3
"""
Fix x/y coordinate units in a Surfdata-style NetCDF:
- Set lon variable units to 'meter' (it is projection x)
- Set lat variable units to 'meter' (it is projection y)
Does not touch LATIXY/LONGXY (which remain in degrees).

Example:
  python3 NA_surfdataGEN/NADaymet/dataProduct_DOI/fix_xy_units.py \
    --in  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_and_temp.nc \
    --out /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_and_temp.fixed_units.nc
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List

try:
    import xarray as xr
except Exception:
    print("ERROR: xarray is required. Install with: pip install xarray netCDF4 h5netcdf", file=sys.stderr)
    raise


def try_open(path: str):
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
    p = argparse.ArgumentParser(description="Set lon/lat variable units to 'meter'")
    p.add_argument("--in", dest="in_path", required=True, help="Input NetCDF")
    p.add_argument("--out", dest="out_path", required=True, help="Output NetCDF")
    args = p.parse_args()

    ds = try_open(args.in_path)

    # Update units on lon/lat coord variables if present
    updates = {}
    for name in ("lon", "lat"):
        if name in ds.variables:
            da = ds[name]
            attrs = dict(da.attrs)
            attrs["units"] = "meter"
            updates[name] = da.assign_attrs(attrs)
    if updates:
        ds = ds.assign(updates)

    os.makedirs(os.path.dirname(args.out_path), exist_ok=True)
    ds.to_netcdf(args.out_path)
    print(f"Wrote: {args.out_path}")


if __name__ == "__main__":
    main()


