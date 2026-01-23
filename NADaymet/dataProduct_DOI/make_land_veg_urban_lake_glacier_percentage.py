#!/usr/bin/env python3
"""
Create land_veg_urban_lake_glacier_percentage.nc including glacier in totals.

Inputs:
- ELM_PFTs/ELM_PFT_output/combined_pft_urban_lake_glacier_total_count.nc

Outputs:
- land_veg_urban_lake_glacier_percentage.nc with:
  - Counts (i2): pft_total_count, urban_count, lake_count, glacier_count, total_count
  - Percentages (f4): pft_percentage, urban_percentage, lake_percentage, glacier_percentage
  - Land fraction (f4): 100% if total_count >= 1089 else total_count/1156*100, NaN for non-land (<0)
"""
from __future__ import annotations

import argparse
import os
import sys
import numpy as np
from netCDF4 import Dataset


def main() -> None:
    p = argparse.ArgumentParser(description="Build land_veg_urban_lake_glacier_percentage.nc (includes glacier)")
    p.add_argument("--in", dest="in_path", required=True, help="Path to combined_pft_urban_lake_glacier_total_count.nc")
    p.add_argument("--out", dest="out_path", required=True, help="Output path for land_veg_urban_lake_glacier_percentage.nc")
    args = p.parse_args()

    with Dataset(args.in_path, "r") as src:
        pft_total_count = src.variables["pft_total_count"][:]
        urban_count = src.variables["urban_count"][:]
        lake_count = src.variables["lake_count"][:]
        glacier_count = src.variables["glacier_count"][:]

    total_count = pft_total_count + urban_count + lake_count + glacier_count

    with np.errstate(divide="ignore", invalid="ignore"):
        pft_percentage = np.where(total_count > 0, (pft_total_count / total_count) * 100.0, np.nan)
        urban_percentage = np.where(total_count > 0, (urban_count / total_count) * 100.0, np.nan)
        lake_percentage = np.where(total_count > 0, (lake_count / total_count) * 100.0, np.nan)
        glacier_percentage = np.where(total_count > 0, (glacier_count / total_count) * 100.0, np.nan)
        land_fraction = np.where(
            total_count < 0,
            np.nan,
            np.where(total_count >= 1089, 100.0, (total_count / 1156.0) * 100.0),
        )

    # Cast dtypes
    pft_total_count = pft_total_count.astype(np.int16, copy=False)
    urban_count = urban_count.astype(np.int16, copy=False)
    lake_count = lake_count.astype(np.int16, copy=False)
    glacier_count = glacier_count.astype(np.int16, copy=False)
    total_count = total_count.astype(np.int16, copy=False)
    pft_percentage = pft_percentage.astype(np.float32, copy=False)
    urban_percentage = urban_percentage.astype(np.float32, copy=False)
    lake_percentage = lake_percentage.astype(np.float32, copy=False)
    glacier_percentage = glacier_percentage.astype(np.float32, copy=False)
    land_fraction = land_fraction.astype(np.float32, copy=False)

    nfiles, ny, nx = total_count.shape
    os.makedirs(os.path.dirname(args.out_path), exist_ok=True)
    with Dataset(args.out_path, "w", format="NETCDF4") as dst:
        dst.createDimension("file", nfiles)
        dst.createDimension("y", ny)
        dst.createDimension("x", nx)

        # Counts
        v = dst.createVariable("pft_total_count", "i2", ("file", "y", "x"), zlib=True, complevel=5); v[:] = pft_total_count
        v.units = "count"; v.long_name = "Total PFT pixel count per gridcell"

        v = dst.createVariable("urban_count", "i2", ("file", "y", "x"), zlib=True, complevel=5); v[:] = urban_count
        v.units = "count"; v.long_name = "Urban pixel count per gridcell"

        v = dst.createVariable("lake_count", "i2", ("file", "y", "x"), zlib=True, complevel=5); v[:] = lake_count
        v.units = "count"; v.long_name = "Lake pixel count per gridcell"

        v = dst.createVariable("glacier_count", "i2", ("file", "y", "x"), zlib=True, complevel=5); v[:] = glacier_count
        v.units = "count"; v.long_name = "Glacier pixel count per gridcell"

        v = dst.createVariable("total_count", "i2", ("file", "y", "x"), zlib=True, complevel=5); v[:] = total_count
        v.units = "count"; v.long_name = "Total pixel count per gridcell (PFT+Urban+Lake+Glacier)"

        # Percentages
        v = dst.createVariable("pft_percentage", "f4", ("file", "y", "x"), zlib=True, complevel=5, fill_value=np.nan); v[:] = pft_percentage
        v.units = "percent"; v.long_name = "PFT percentage of (PFT+Urban+Lake+Glacier)"

        v = dst.createVariable("urban_percentage", "f4", ("file", "y", "x"), zlib=True, complevel=5, fill_value=np.nan); v[:] = urban_percentage
        v.units = "percent"; v.long_name = "Urban percentage of (PFT+Urban+Lake+Glacier)"

        v = dst.createVariable("lake_percentage", "f4", ("file", "y", "x"), zlib=True, complevel=5, fill_value=np.nan); v[:] = lake_percentage
        v.units = "percent"; v.long_name = "Lake percentage of (PFT+Urban+Lake+Glacier)"

        v = dst.createVariable("glacier_percentage", "f4", ("file", "y", "x"), zlib=True, complevel=5, fill_value=np.nan); v[:] = glacier_percentage
        v.units = "percent"; v.long_name = "Glacier percentage of (PFT+Urban+Lake+Glacier)"

        v = dst.createVariable("land_fraction", "f4", ("file", "y", "x"), zlib=True, complevel=5, fill_value=np.nan); v[:] = land_fraction
        v.units = "percent"; v.long_name = "Estimated land fraction per gridcell based on total_count"

    print(f"Saved: {args.out_path}")


if __name__ == "__main__":
    main()

