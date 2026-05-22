#!/usr/bin/env python3
"""
Correct Great Lakes lake fractions in a Daymet NALCMS surfdata file.

Root cause
----------
NALCMS maps open water in the Great Lakes to class 14 (Wetland), not class 18
(Water). The standard pipeline counts only class 18 as lake, so Great Lakes
cells appear as wetland vegetation (PFT 13) or as ocean/no-data when counts
are missing after grid cropping.

Fix
---
For grid cells whose centers fall inside Great Lakes polygons (Natural Earth
10m lakes), reclassify NALCMS class-14 pixel counts as lake:

  lake_count  += wetland14_count
  pft_total   -= wetland14_count
  total_count  = urban + lake + glacier + pft_total  (recomputed)

Percent fields (PCT_LAKE, PCT_NATVEG, PCT_NAT_PFT) are recomputed from the
updated counts. PFT 13 (wetland) is reduced in proportion to the transferred
wetland count.

Example
-------
python3 fix_great_lakes_lake_mask.py \\
  --in-file  /path/to/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc \\
  --out-file /path/to/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc \\
  --landtype14-tif /path/to/landtype14_count_in_namask.tif
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Iterable, Tuple
from urllib.request import urlopen

import geopandas as gpd
import numpy as np
import rasterio
import xarray as xr
from shapely.geometry import Point

DEFAULT_LANDTYPE14_TIF = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/"
    "NADaymet/landtype14_count_in_namask.tif"
)
DEFAULT_IN_FILE = Path(
    "/Users/7xw/Documents/Work/papers/NALCMS_sn-article/"
    "DaymetVeg_LandUnit_DataProduct/"
    "surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc"
)

GREAT_LAKE_NAMES = (
    "Lake Superior",
    "Lake Michigan",
    "Lake Huron",
    "Lake Erie",
    "Lake Ontario",
)
NE_LAKES_URL = "https://naciscdn.org/naturalearth/10m/physical/ne_10m_lakes.zip"
FILL_I16 = np.int16(-32767)


def load_great_lakes_polygons(cache_dir: Path | None = None) -> gpd.GeoDataFrame:
    cache_dir = cache_dir or Path(__file__).resolve().parent / "great_lakes_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    shp_path = cache_dir / "ne_10m_lakes.shp"

    if not shp_path.exists():
        print(f"Downloading Natural Earth lakes: {NE_LAKES_URL}")
        with urlopen(NE_LAKES_URL, timeout=120) as resp:
            zdata = resp.read()
        with zipfile.ZipFile(BytesIO(zdata)) as zf:
            zf.extractall(cache_dir)

    lakes = gpd.read_file(shp_path)
    if "name" not in lakes.columns:
        raise KeyError(f"'name' column missing in {shp_path}; columns={list(lakes.columns)}")

    gl = lakes[lakes["name"].isin(GREAT_LAKE_NAMES)].copy()
    if gl.empty:
        raise RuntimeError(
            f"No Great Lakes features found in Natural Earth lakes file. "
            f"Expected one of: {GREAT_LAKE_NAMES}"
        )
    print(f"Loaded Great Lakes polygons: {', '.join(gl['name'].tolist())}")
    return gl


def sample_landtype_counts(
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    mask: np.ndarray,
    landtype_tif: Path,
) -> np.ndarray:
    """Sample per-class pixel counts using Daymet projected x/y (meters)."""
    out = np.zeros(x_grid.shape, dtype=np.int32)
    idx = np.argwhere(mask)
    if idx.size == 0:
        return out

    xs = np.array([float(x_grid[j, i]) for j, i in idx], dtype=np.float64)
    ys = np.array([float(y_grid[j, i]) for j, i in idx], dtype=np.float64)
    with rasterio.open(landtype_tif) as src:
        rows, cols = rasterio.transform.rowcol(src.transform, xs, ys)
        data = src.read(1)
        for k, (j, i) in enumerate(idx):
            r, c = int(rows[k]), int(cols[k])
            if 0 <= r < data.shape[0] and 0 <= c < data.shape[1]:
                val = int(data[r, c])
                out[j, i] = val if val > 0 else 0
    return out


def sample_landtype14_counts(
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    mask: np.ndarray,
    landtype14_tif: Path,
) -> np.ndarray:
    return sample_landtype_counts(x_grid, y_grid, mask, landtype14_tif)


def build_great_lakes_mask(
    lon: np.ndarray,
    lat: np.ndarray,
    gl_gdf: gpd.GeoDataFrame,
    buffer_m: float = 0.0,
) -> np.ndarray:
    valid = np.isfinite(lon) & np.isfinite(lat)
    if gl_gdf.crs is None:
        gl_poly = gl_gdf.set_crs("EPSG:4326")
    elif gl_gdf.crs.to_epsg() != 4326:
        gl_poly = gl_gdf.to_crs("EPSG:4326")
    else:
        gl_poly = gl_gdf

    if buffer_m > 0:
        gl_poly = gl_poly.to_crs(3857)
        gl_poly = gl_poly.copy()
        gl_poly["geometry"] = gl_poly.geometry.buffer(buffer_m)
        gl_poly = gl_poly.to_crs("EPSG:4326")

    minx, miny, maxx, maxy = gl_poly.total_bounds
    bbox = valid & (lon >= minx) & (lon <= maxx) & (lat >= miny) & (lat <= maxy)
    idx = np.argwhere(bbox)
    if idx.size == 0:
        return np.zeros(lon.shape, dtype=bool)

    points = gpd.GeoDataFrame(
        geometry=[Point(float(lon[j, i]), float(lat[j, i])) for j, i in idx],
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(points, gl_poly[["geometry"]], how="inner", predicate="within")
    mask = np.zeros(lon.shape, dtype=bool)
    for k in joined.index:
        j, i = idx[k]
        mask[j, i] = True
    return mask


def recompute_percentages(
    lake_count: np.ndarray,
    pft_total_count: np.ndarray,
    urban_count: np.ndarray,
    glacier_count: np.ndarray,
    pct_nat_pft: np.ndarray,
    pct_urban: np.ndarray,
    pct_glacier: np.ndarray,
    natpft: Iterable[int],
    update_mask: np.ndarray,
    transfer: np.ndarray,
    pct_lake_base: np.ndarray,
    pct_veg_base: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    pct_lake = pct_lake_base.astype(np.float32).copy()
    pct_veg = pct_veg_base.astype(np.float32).copy()
    pct_out = pct_nat_pft.astype(np.float32).copy()
    pct_urban_out = pct_urban.astype(np.float32).copy()
    pct_glacier_out = pct_glacier.astype(np.float32).copy()

    natpft_list = list(natpft)
    pft13_idx = natpft_list.index(13) if 13 in natpft_list else None

    total = (
        lake_count.astype(np.float64)
        + pft_total_count.astype(np.float64)
        + urban_count.astype(np.float64)
        + glacier_count.astype(np.float64)
    )

    for j, i in np.argwhere(update_mask):
        t = total[j, i]
        if t <= 0:
            pct_lake[j, i] = np.nan
            pct_veg[j, i] = np.nan
            pct_glacier_out[j, i] = np.nan
            pct_urban_out[:, j, i] = 0.0
            pct_out[:, j, i] = 0.0
            continue

        pct_lake[j, i] = np.float32(lake_count[j, i] / t * 100.0)
        pct_veg[j, i] = np.float32(pft_total_count[j, i] / t * 100.0)
        pct_glacier_out[j, i] = np.float32(glacier_count[j, i] / t * 100.0)
        urban_frac = np.float32(urban_count[j, i] / t * 100.0)
        pct_urban_out[:, j, i] = 0.0
        pct_urban_out[0, j, i] = urban_frac

        pft_total_new = float(pft_total_count[j, i])
        if pft_total_new <= 0:
            pct_out[:, j, i] = 0.0
            continue

        moved = float(transfer[j, i])
        pft_total_old = pft_total_new + moved
        if pft_total_old <= 0:
            pct_out[:, j, i] = 0.0
            continue

        old_pft = np.array([float(pct_out[k, j, i]) for k in range(len(natpft_list))], dtype=np.float64)
        old_pft = np.where(np.isfinite(old_pft) & (old_pft >= 0.0) & (old_pft <= 100.0), old_pft, 0.0)
        old_sum = old_pft.sum()
        if old_sum <= 0:
            pct_out[:, j, i] = 0.0
            continue

        pft_counts = old_pft / old_sum * pft_total_old
        if pft13_idx is not None:
            pft_counts[pft13_idx] = max(0.0, pft_counts[pft13_idx] - moved)
        count_sum = pft_counts.sum()
        if count_sum <= 0:
            pct_out[:, j, i] = 0.0
        else:
            pct_out[:, j, i] = (pft_counts / count_sum * 100.0).astype(np.float32)

    return pct_lake, pct_veg, pct_out, pct_urban_out, pct_glacier_out


def apply_great_lakes_fix(
    in_file: Path,
    out_file: Path,
    landtype14_tif: Path,
    cache_dir: Path | None,
    buffer_m: float = 10000.0,
    landtype18_tif: Path | None = None,
) -> dict:
    if not landtype14_tif.is_file():
        raise FileNotFoundError(f"landtype14 tif not found: {landtype14_tif}")

    gl_gdf = load_great_lakes_polygons(cache_dir)
    ds = xr.open_dataset(in_file)
    lon = ds["LONGXY"].values
    lat = ds["LATIXY"].values
    x_grid, y_grid = np.meshgrid(ds["x"].values, ds["y"].values)

    gl_mask = build_great_lakes_mask(lon, lat, gl_gdf, buffer_m=buffer_m)
    wetland14 = sample_landtype14_counts(x_grid, y_grid, gl_mask, landtype14_tif)
    transfer = np.where(gl_mask, wetland14, 0).astype(np.int32)

    if landtype18_tif is None:
        landtype18_tif = landtype14_tif.with_name("landtype18_count_in_namask.tif")
    water18 = (
        sample_landtype_counts(x_grid, y_grid, gl_mask, landtype18_tif)
        if landtype18_tif.is_file()
        else np.zeros(lon.shape, dtype=np.int32)
    )

    lake_count = ds["lake_count"].values.astype(np.int32).copy()
    pft_total_count = ds["pft_total_count"].values.astype(np.int32).copy()
    urban_count = ds["urban_count"].values.astype(np.int32).copy()
    glacier_count = ds["glacier_count"].values.astype(np.int32).copy()
    total_count = ds["total_count"].values.astype(np.int32).copy()
    pct_nat_pft = ds["PCT_NAT_PFT"].values
    pct_lake_base = ds["PCT_LAKE"].values
    pct_veg_base = ds["PCT_NATVEG"].values
    pct_urban_base = ds["PCT_URBAN"].values
    pct_glacier_base = ds["PCT_GLACIER"].values

    fill_mask = (lake_count == FILL_I16) | (total_count == FILL_I16)
    urban_count[urban_count == FILL_I16] = 0
    glacier_count[glacier_count == FILL_I16] = 0
    lake_count[fill_mask] = 0
    pft_total_count[fill_mask] = 0

    transfer_cells = transfer > 0
    n_transfer_cells = int(transfer_cells.sum())
    pixels_moved = int(transfer[transfer_cells].sum())

    lake_count[transfer_cells] += transfer[transfer_cells]
    pft_total_count[transfer_cells] -= transfer[transfer_cells]
    pft_total_count = np.maximum(pft_total_count, 0)

    # Cells with class-18 water counts but missing surfdata totals (cropped open water).
    water18_cells = gl_mask & (water18 > 0) & (lake_count == 0) & (pft_total_count == 0)
    lake_count[water18_cells] = water18[water18_cells]

    # Remaining open-water holes inside the buffered lake mask: no class counts after crop.
    open_water_holes = (
        gl_mask
        & (lake_count == 0)
        & (pft_total_count == 0)
        & (urban_count == 0)
        & (glacier_count == 0)
    )
    if open_water_holes.any():
        lake_count[open_water_holes] = 1000

    total_count = lake_count + pft_total_count + urban_count + glacier_count
    update_mask = gl_mask & (total_count > 0)

    pct_lake, pct_veg, pct_nat_pft, pct_urban, pct_glacier = recompute_percentages(
        lake_count=lake_count,
        pft_total_count=pft_total_count,
        urban_count=urban_count,
        glacier_count=glacier_count,
        pct_nat_pft=pct_nat_pft,
        pct_urban=pct_urban_base,
        pct_glacier=pct_glacier_base,
        natpft=ds["natpft"].values,
        update_mask=update_mask,
        transfer=transfer,
        pct_lake_base=pct_lake_base,
        pct_veg_base=pct_veg_base,
    )

    # Restore fill values where land total remains zero.
    no_land = (total_count <= 0) & ~update_mask
    lake_count[no_land] = FILL_I16
    pft_total_count[no_land] = FILL_I16
    urban_count[no_land] = FILL_I16
    glacier_count[no_land] = FILL_I16
    total_count[no_land] = FILL_I16

    out = ds.copy(deep=True)
    out["lake_count"].values = lake_count.astype(np.int16)
    out["pft_total_count"].values = pft_total_count.astype(np.int16)
    out["urban_count"].values = urban_count.astype(np.int16)
    out["glacier_count"].values = glacier_count.astype(np.int16)
    out["total_count"].values = total_count.astype(np.int16)
    out["PCT_LAKE"].values = pct_lake
    out["PCT_NATVEG"].values = pct_veg
    out["PCT_NAT_PFT"].values = pct_nat_pft
    out["PCT_URBAN"].values = pct_urban
    out["PCT_GLACIER"].values = pct_glacier

    out.attrs["great_lakes_fix"] = (
        "Reclassified NALCMS class-14 wetland counts to lake inside buffered Great "
        f"Lakes polygons (Natural Earth 10m lakes, buffer={buffer_m:g} m). "
        "Assigned 100% lake to cropped open-water cells with missing class counts."
    )
    out.attrs["great_lakes_fix_buffer_m"] = float(buffer_m)
    out.attrs["great_lakes_fix_source"] = str(landtype14_tif)
    out.attrs["great_lakes_fix_script"] = str(Path(__file__).name)

    encoding = {name: {"zlib": True, "complevel": 5} for name in out.data_vars}
    out.to_netcdf(out_file, encoding=encoding)
    ds.close()
    out.close()

    stats = {
        "gl_mask_cells": int(gl_mask.sum()),
        "transfer_cells": n_transfer_cells,
        "wetland_pixels_reclassified": pixels_moved,
        "output": str(out_file),
    }
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fix Great Lakes lake land unit in NALCMS Daymet surfdata."
    )
    parser.add_argument("--in-file", type=Path, default=DEFAULT_IN_FILE)
    parser.add_argument("--out-file", type=Path, required=True)
    parser.add_argument("--landtype14-tif", type=Path, default=DEFAULT_LANDTYPE14_TIF)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Directory to cache Natural Earth Great Lakes shapefile",
    )
    parser.add_argument(
        "--buffer-m",
        type=float,
        default=15000.0,
        help="Buffer (meters) applied to Great Lakes polygons before grid selection",
    )
    parser.add_argument(
        "--landtype18-tif",
        type=Path,
        default=None,
        help="Optional class-18 water count GeoTIFF (defaults next to landtype14 tif)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        stats = apply_great_lakes_fix(
            in_file=args.in_file,
            out_file=args.out_file,
            landtype14_tif=args.landtype14_tif,
            cache_dir=args.cache_dir,
            buffer_m=args.buffer_m,
            landtype18_tif=args.landtype18_tif,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("Great Lakes fix applied:")
    for key, val in stats.items():
        print(f"  {key}: {val}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
