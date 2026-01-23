#!/usr/bin/env python3
"""
Crop land_veg_urban_lake_glacier_percentage.nc to match Surfdata lat/lon grid using
pixel offsets (dx, dy), then optionally merge into a single NetCDF.

Example:
  python3 NA_surfdataGEN/NADaymet/dataProduct_DOI/crop_align_merge.py \
    --surf-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc \
    --land-file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/land_veg_urban_lake_glacier_percentage.nc \
    --dx 98 --dy 72 \
    --out-cropped /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/land_veg_urban_lake_glacier_percentage.cropped_to_surfdata.nc \
    --out-merged  /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/surfdata_with_land_veg_urban_lake_glacier.nc
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List

import numpy as np

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
    p = argparse.ArgumentParser(description="Crop land_veg file to Surfdata grid and optionally merge")
    p.add_argument("--surf-file", required=True, help="Path to Surfdata NetCDF")
    p.add_argument("--land-file", required=True, help="Path to land_veg_urban_lake_percentage NetCDF")
    p.add_argument("--dx", required=True, type=int, help="x offset (columns) into land_veg to start crop")
    p.add_argument("--dy", required=True, type=int, help="y offset (rows) into land_veg to start crop")
    p.add_argument("--out-cropped", required=True, help="Output NetCDF for cropped land_veg aligned to Surfdata")
    p.add_argument("--out-merged", default=None, help="Optional output NetCDF for merged Surfdata + cropped land_veg")
    args = p.parse_args()

    surf = try_open(args.surf_file)
    land = try_open(args.land_file)

    # Surfdata sizes
    lat_dim = "lat"
    lon_dim = "lon"
    if lat_dim not in surf.dims or lon_dim not in surf.dims:
        print(f"ERROR: Surfdata missing expected dims 'lat' and 'lon' (found {list(surf.dims)})", file=sys.stderr)
        sys.exit(2)
    nlat = surf.sizes[lat_dim]
    nlon = surf.sizes[lon_dim]

    # Land dims: accept either (y,x) or already-aligned (lat,lon)
    cropped = None
    if "y" in land.dims and "x" in land.dims:
        ny = land.sizes["y"]
        nx = land.sizes["x"]
        start_y = args.dy
        start_x = args.dx
        end_y = start_y + nlat
        end_x = start_x + nlon
        if start_y < 0 or start_x < 0 or end_y > ny or end_x > nx:
            print(
                f"ERROR: crop window out of bounds: y[{start_y}:{end_y}] x[{start_x}:{end_x}] "
                f"for land dims y={ny}, x={nx}",
                file=sys.stderr,
            )
            sys.exit(2)
        cropped_vars = {}
        for name, da in land.data_vars.items():
            dims = da.dims
            if len(dims) >= 2 and dims[-2:] == ("y", "x"):
                sel = da.isel(y=slice(start_y, end_y), x=slice(start_x, end_x))
                if "file" in sel.dims and sel.sizes.get("file", 1) == 1:
                    sel = sel.isel(file=0, drop=True)
                sel = sel.rename({"y": "lat", "x": "lon"})
                cropped_vars[name] = sel
        if not cropped_vars:
            print("ERROR: no variables with trailing (y, x) dims found to crop", file=sys.stderr)
            sys.exit(2)
        cropped = xr.Dataset(cropped_vars)
    elif "lat" in land.dims and "lon" in land.dims:
        # Already aligned/cropped to Surfdata grid; just normalize variable dims and drop singleton file dim
        if land.sizes["lat"] != nlat or land.sizes["lon"] != nlon:
            print(
                f"ERROR: land(lat,lon)={land.sizes['lat']},{land.sizes['lon']} does not match surf(lat,lon)={nlat},{nlon}",
                file=sys.stderr,
            )
            sys.exit(2)
        normalized_vars = {}
        for name, da in land.data_vars.items():
            sel = da
            if "file" in sel.dims and sel.sizes.get("file", 1) == 1:
                sel = sel.isel(file=0, drop=True)
            # Ensure last two dims are (lat, lon) if present
            normalized_vars[name] = sel
        cropped = xr.Dataset(normalized_vars)
    else:
        print(f"ERROR: land file has unsupported dims {list(land.dims)}; expected (y,x) or (lat,lon)", file=sys.stderr)
        sys.exit(2)
    # Attach Surfdata 1D coords so alignment is exact
    if "lat" in surf and "lon" in surf:
        lat = surf["lat"].copy()
        lon = surf["lon"].copy()
        # Ensure projected units are meters
        lat.attrs = dict(lat.attrs)
        lon.attrs = dict(lon.attrs)
        lat.attrs["units"] = "meter"
        lon.attrs["units"] = "meter"
        cropped = cropped.assign_coords(lat=lat, lon=lon)

    # Write cropped file
    os.makedirs(os.path.dirname(args.out_cropped), exist_ok=True)
    encoding = {v: {"zlib": True, "complevel": 4} for v in cropped.data_vars}
    cropped.to_netcdf(args.out_cropped, encoding=encoding)
    print(f"Wrote cropped: {args.out_cropped}")

    # Optionally merge with Surfdata
    if args.out_merged:
        # Avoid duplicate coord variables in the output by dropping from one side if needed
        # Keep Surfdata coords authoritative
        cropped_for_merge = cropped.drop_vars([k for k in ("lat", "lon") if k in cropped.variables], errors="ignore")
        merged = xr.merge([surf, cropped_for_merge], compat="override", join="exact")
        # Ensure units on lat/lon are meters in merged as well
        if "lat" in merged and "lon" in merged:
            merged["lat"].attrs = dict(merged["lat"].attrs, units="meter")
            merged["lon"].attrs = dict(merged["lon"].attrs, units="meter")
        encoding2 = {v: {"zlib": True, "complevel": 4} for v in merged.data_vars if v not in ("lat", "lon")}
        merged.to_netcdf(args.out_merged, encoding=encoding2)
        print(f"Wrote merged: {args.out_merged}")


if __name__ == "__main__":
    main()


