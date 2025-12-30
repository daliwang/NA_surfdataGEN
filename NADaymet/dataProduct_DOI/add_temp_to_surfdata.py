#!/usr/bin/env python3
"""
Add AvgTemp from mean_temperature_coldest_month.nc into a Surfdata file,
renaming to AvgTempColdMonth, aligning dims (y,x)->(lat,lon), and assigning
Surfdata lat/lon coordinates for exact alignment.

Example:
  python3 NA_surfdataGEN/NADaymet/dataProduct_DOI/add_temp_to_surfdata.py \
    --surf-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake.nc \
    --temp-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/ELM_PFTs/mean_temperature_coldest_month.nc \
    --out-file  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_and_temp.nc
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
    raise RuntimeError(f"Failed to open {path} with any engine:\n" + "\n".join(errors))


def main() -> None:
    p = argparse.ArgumentParser(description="Merge AvgTemp into Surfdata as AvgTempColdMonth")
    p.add_argument("--surf-file", required=True, help="Path to Surfdata NetCDF (target)")
    p.add_argument("--temp-file", required=True, help="Path to mean_temperature_coldest_month.nc")
    p.add_argument("--out-file", required=True, help="Output path for merged NetCDF")
    args = p.parse_args()

    surf = try_open(args.surf_file)
    temp = try_open(args.temp_file)

    # Expect temp to have variables: AvgTemp(y,x) and coords x(x), y(y)
    if "AvgTemp" not in temp.data_vars:
        print("ERROR: 'AvgTemp' not found in temperature file.", file=sys.stderr)
        sys.exit(2)
    avg = temp["AvgTemp"]
    # Keep original coord vectors for orientation checks
    y_temp = temp["y"] if "y" in temp.variables else None
    x_temp = temp["x"] if "x" in temp.variables else None

    # Rename dims to match Surfdata
    rename_dims = {}
    if "y" in avg.dims:
        rename_dims["y"] = "lat"
    if "x" in avg.dims:
        rename_dims["x"] = "lon"
    avg = avg.rename(rename_dims)

    # Verify sizes match Surfdata
    for d in ("lat", "lon"):
        if d not in avg.dims or d not in surf.dims:
            print(f"ERROR: missing dim {d} in one of the files.", file=sys.stderr)
            sys.exit(2)
        if avg.sizes[d] != surf.sizes[d]:
            print(
                f"ERROR: dimension mismatch on {d}: temp={avg.sizes[d]} vs surf={surf.sizes[d]}",
                file=sys.stderr,
            )
            sys.exit(2)

    # If temp orientation (in x/y) is opposite to Surfdata (in lon/lat), flip data
    def orientation(vals) -> int:
        try:
            v0 = float(vals[0])
            v1 = float(vals[-1])
            if np.isnan(v0) or np.isnan(v1):
                return 0
            return 1 if v0 < v1 else -1
        except Exception:
            return 0

    try:
        import numpy as np  # local import to avoid top-level dependency if unused
    except Exception:
        pass

    lat_surf = surf["lat"] if "lat" in surf.variables else None
    lon_surf = surf["lon"] if "lon" in surf.variables else None

    # Compare directions only if both sides have 1D coord vectors
    if y_temp is not None and lat_surf is not None and y_temp.ndim == 1 and lat_surf.ndim == 1:
        oy = orientation(y_temp.values)
        oly = orientation(lat_surf.values)
        if oy != 0 and oly != 0 and oy != oly:
            avg = avg.isel(lat=slice(None, None, -1))

    if x_temp is not None and lon_surf is not None and x_temp.ndim == 1 and lon_surf.ndim == 1:
        ox = orientation(x_temp.values)
        olx = orientation(lon_surf.values)
        if ox != 0 and olx != 0 and ox != olx:
            avg = avg.isel(lon=slice(None, None, -1))

    # Attach Surfdata coordinates so the grids are identical
    if "lat" in surf and "lon" in surf:
        avg = avg.assign_coords(lat=surf["lat"], lon=surf["lon"])

    # Rename variable and set attributes
    avg = avg.rename("AvgTempColdMonth")
    attrs = dict(avg.attrs)
    attrs.setdefault("long_name", "Average temperature of coldest month")
    attrs.setdefault("units", "C")
    avg.attrs = attrs

    # Merge into surfdata (drop x/y coord vars from temp if present)
    temp_vars = xr.Dataset({"AvgTempColdMonth": avg})
    merged = xr.merge([surf, temp_vars], compat="override", join="exact")

    # Write output with compression
    encoding = {v: {"zlib": True, "complevel": 4} for v in merged.data_vars if v not in ("lat", "lon")}
    os.makedirs(os.path.dirname(args.out_file), exist_ok=True)
    merged.to_netcdf(args.out_file, encoding=encoding)
    print(f"Wrote merged file: {args.out_file}")


if __name__ == "__main__":
    main()


