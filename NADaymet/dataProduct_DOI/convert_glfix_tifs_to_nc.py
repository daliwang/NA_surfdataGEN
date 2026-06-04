#!/usr/bin/env python3
"""
Convert landtype*_count_in_namask_glfix.tif into landtype*_nalcms_*_in_daymet.nc.

Writes NetCDFs into NADaymet/landtypes_count without plotting.
"""
from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import rasterio
from netCDF4 import Dataset


CLASS_MAPPING = {
    1: "Temperate_needleleaf",
    2: "Taiga_needleleaf",
    3: "Tropical_evergreen",
    4: "Tropical_deciduous",
    5: "Temperate_deciduous",
    6: "Mixed_forrest",
    7: "Tropical_shrub",
    8: "Temperate_shrub",
    9: "Tropical_grass",
    10: "Temperate_grass",
    11: "Polar_shrub_moss",
    12: "Polar_grass_moss",
    13: "Polar_barren_moss",
    14: "Wetland",
    15: "Cropland",
    16: "Barren_land",
    17: "Urban",
    18: "Water",
    19: "Snow_Ice",
}


def main() -> None:
    nad_root = Path(__file__).resolve().parents[1]
    out_dir = nad_root / "landtypes_count"
    tif_files = sorted(nad_root.glob("landtype*_count_in_namask_glfix.tif"))
    if not tif_files:
        raise SystemExit("No landtype*_count_in_namask_glfix.tif files found.")
    out_dir.mkdir(parents=True, exist_ok=True)

    for tif_file in tif_files:
        match = re.search(r"landtype(\\d+)_count_in_namask_glfix\\.tif", tif_file.name)
        if not match:
            continue
        group_id = int(match.group(1))
        class_name = CLASS_MAPPING.get(group_id)
        if class_name is None:
            continue

        with rasterio.open(tif_file) as src:
            data = src.read(1).astype(np.float32)
            mask = src.read_masks(1)
        data[mask == 0] = np.nan

        nc_filename = out_dir / f"landtype{group_id}_nalcms_{class_name}_in_daymet.nc"
        with Dataset(nc_filename, "w", format="NETCDF4") as nc:
            nc.createDimension("y", data.shape[0])
            nc.createDimension("x", data.shape[1])
            landtype_var = nc.createVariable(
                "landtype_count",
                "f4",
                ("y", "x"),
                fill_value=np.nan,
                zlib=True,
                complevel=5,
            )
            landtype_var[:, :] = data
            landtype_var.units = "count"
            landtype_var.long_name = f"Landtype {group_id} ({class_name}) count per gridcell"
            nc.description = f"Landtype {group_id} ({class_name}) count from {tif_file.name}"
        print(f"Wrote {nc_filename}")


if __name__ == "__main__":
    main()
