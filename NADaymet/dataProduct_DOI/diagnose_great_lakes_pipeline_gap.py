#!/usr/bin/env python3
"""
Diagnose why Great Lakes open-water cells lose lake fractions in 1-km surfdata.

The 30 m NALCMS source (nalcms2daymet_hcompressed.tif) maps Great Lakes open
water as class 18 (Water). Gaps in surfdata arise from the counting pipeline:

1. na_mask.tif marks many open-lake 1 km cells as mask=0 (outside land domain).
   class_count_na_para.py only aggregates 30 m pixels where na_mask==1, so
   class-18 counts stay -1 in landtype18_count_in_namask.tif.

2. For na_mask==1 water-dominated cells, pft_total_count is summed across all
   PFT layers with -1 sentinels for absent classes, yielding large negative
   totals (e.g. -22) that propagate as non-land in combined count files.

3. crop_align_merge.py (dx/dy window) and int16 fill (-32767) encoding then
   produce NaN percentages and missing PCT_LAKE in the final surfdata product.

Example:
  python3 diagnose_great_lakes_pipeline_gap.py \\
    --surfdata-file /path/to/surfdata...c260128.nc
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
import xarray as xr

DEFAULT_SURFDATA = Path(
    "/Users/7xw/Documents/Work/papers/NALCMS_sn-article/"
    "DaymetVeg_LandUnit_DataProduct/"
    "surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc"
)
DEFAULT_NA_MASK = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/"
    "NADaymet/entire_domain/na_mask.tif"
)
DEFAULT_NALCMS_30M = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/"
    "NADaymet/entire_domain/nalcms2daymet_hcompressed.tif"
)
DEFAULT_T18 = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/"
    "NADaymet/landtype18_count_in_namask.tif"
)
DEFAULT_T14 = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/"
    "NADaymet/landtype14_count_in_namask.tif"
)
FILL_I16 = -32767


def sample_raster(path: Path, x: float, y: float) -> int | None:
    with rasterio.open(path) as src:
        row, col = src.index(x, y)
        if 0 <= row < src.height and 0 <= col < src.width:
            return int(src.read(1, window=((row, row + 1), (col, col + 1)))[0, 0])
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surfdata-file", type=Path, default=DEFAULT_SURFDATA)
    parser.add_argument("--na-mask", type=Path, default=DEFAULT_NA_MASK)
    parser.add_argument("--nalcms-30m", type=Path, default=DEFAULT_NALCMS_30M)
    parser.add_argument("--landtype18-tif", type=Path, default=DEFAULT_T18)
    parser.add_argument("--landtype14-tif", type=Path, default=DEFAULT_T14)
    args = parser.parse_args()

    ds = xr.open_dataset(args.surfdata_file, engine="netcdf4")
    lon = ds["LONGXY"].values
    lat = ds["LATIXY"].values
    x = ds["x"].values
    y = ds["y"].values
    valid = np.isfinite(lon) & np.isfinite(lat)
    fill = np.isnan(ds["PCT_LAKE"].values) & (ds["total_count"].values == FILL_I16)
    gl_box = valid & (lon >= -92) & (lon <= -76) & (lat >= 41) & (lat <= 49)
    gl_fill = fill & gl_box
    n_gl_fill = int(gl_fill.sum())
    print(f"Surfdata file: {args.surfdata_file}")
    print(f"Great Lakes bbox fill cells (missing PCT_LAKE): {n_gl_fill}")

    idx = np.argwhere(gl_fill)
    na_vals = np.zeros(len(idx), dtype=np.int8)
    t18_vals = np.full(len(idx), -999, dtype=np.int32)
    t14_vals = np.full(len(idx), -999, dtype=np.int32)
    src_vals = np.full(len(idx), -999, dtype=np.int32)

    xs = np.array([float(x[i]) for _, i in idx], dtype=np.float64)
    ys = np.array([float(y[j]) for j, _ in idx], dtype=np.float64)

    def sample_bulk(path: Path, fill: int = -999) -> np.ndarray:
        out = np.full(len(idx), fill, dtype=np.int32)
        with rasterio.open(path) as src:
            rows, cols = rasterio.transform.rowcol(src.transform, xs, ys)
            rows = np.asarray(rows, dtype=np.int64)
            cols = np.asarray(cols, dtype=np.int64)
            valid = (rows >= 0) & (rows < src.height) & (cols >= 0) & (cols < src.width)
            if not np.any(valid):
                return out
            r0, r1 = int(rows[valid].min()), int(rows[valid].max()) + 1
            c0, c1 = int(cols[valid].min()), int(cols[valid].max()) + 1
            from rasterio.windows import Window
            win = Window(c0, r0, c1 - c0, r1 - r0)
            data = src.read(1, window=win)
            out[valid] = data[rows[valid] - r0, cols[valid] - c0].astype(np.int32)
        return out

    na_vals = sample_bulk(args.na_mask, fill=0).astype(np.int8)
    t18_vals = sample_bulk(args.landtype18_tif)
    t14_vals = sample_bulk(args.landtype14_tif)
    src_vals = sample_bulk(args.nalcms_30m)

    print("\nBreakdown of Great Lakes fill cells:")
    print(f"  na_mask==0 (never counted):           {(na_vals == 0).sum():6d} ({100*(na_vals==0).sum()/len(idx):.1f}%)")
    print(f"  na_mask==1 (inside land mask):        {(na_vals == 1).sum():6d} ({100*(na_vals==1).sum()/len(idx):.1f}%)")
    print(f"  class-18 count > 0 (1 km tif):        {(t18_vals > 0).sum():6d}")
    print(f"  class-14 count > 0 (1 km tif):        {(t14_vals > 0).sum():6d}")
    print(f"  30 m source class 18 at cell center:  {(src_vals == 18).sum():6d}")
    print(f"  30 m source class 14 at cell center:  {(src_vals == 14).sum():6d}")
    print(f"  mask==0 & 30m class 18:               {((na_vals==0)&(src_vals==18)).sum():6d}")
    print(f"  mask==1 & t18>0 but surf still fill:  {((na_vals==1)&(t18_vals>0)).sum():6d}")

    print("\nOpen-lake reference points (30 m source vs 1 km pipeline):")
    refs = [
        ("Lake Superior center", -87.0, 47.5),
        ("Lake Michigan center", -87.0, 43.5),
        ("Lake Huron center", -82.5, 44.8),
    ]
    print(f"{'location':24} {'na_mask':>8} {'t18cnt':>8} {'src30m':>8}")
    for name, lo, la in refs:
        d = np.where(valid, (lat - la) ** 2 + (lon - lo) ** 2, np.inf)
        j, i = np.unravel_index(np.argmin(d), d.shape)
        xv, yv = float(x[i]), float(y[j])
        print(
            f"{name:24} {sample_raster(args.na_mask, xv, yv)!s:>8} "
            f"{sample_raster(args.landtype18_tif, xv, yv)!s:>8} "
            f"{sample_raster(args.nalcms_30m, xv, yv)!s:>8}"
        )

    if "pft_total_count" in ds:
        pf = ds["pft_total_count"].values.astype(np.int32)
        uniq, cnt = np.unique(pf[gl_fill], return_counts=True)
        print("\npft_total_count values on Great Lakes fill cells:")
        for u, c in sorted(zip(uniq, cnt), key=lambda t: -t[1])[:5]:
            print(f"  {u}: {c}")

    ds.close()
    print(
        "\nConclusion: open-lake cells are class 18 in the 30 m NALCMS source, "
        "but na_mask==0 excludes most from class counting; remaining cells fail "
        "land-unit assembly because negative PFT sentinels and int16 fill values "
        "prevent lake counts from becoming valid PCT_LAKE."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
