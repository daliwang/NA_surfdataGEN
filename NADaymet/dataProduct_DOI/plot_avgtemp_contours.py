#!/usr/bin/env python3
"""
Contour plotting for AvgTempColdMonth (or other variables) from a surfdata NetCDF.

Examples:
  # Contour lines for a specific temperature
  python3 NADaymet/dataProduct_DOI/plot_avgtemp_contours.py \
    --file /path/to/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c251230.nc \
    --temp-level -10

  # Filled contours for a range (with auto levels)
  python3 NADaymet/dataProduct_DOI/plot_avgtemp_contours.py \
    --file /path/to/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c251230.nc \
    --temp-range -30 10 --save --outdir ./contours

  # Use a specific time index if variable has a time dimension
  python3 NADaymet/dataProduct_DOI/plot_avgtemp_contours.py \
    --file /path/to/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c251230.nc \
    --temp-range -25 5 --time-dim time --time-index 0
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

try:
    import xarray as xr
except Exception:
    print("ERROR: xarray is required. Install with: pip install xarray netCDF4 h5netcdf", file=sys.stderr)
    raise

try:
    import matplotlib
    matplotlib.use("Agg")  # non-interactive by default; enable with --show
    import matplotlib.pyplot as plt
except Exception:
    print("ERROR: matplotlib is required. Install with: pip install matplotlib", file=sys.stderr)
    raise


def try_open_dataset(path: str, engine: Optional[str]) -> xr.Dataset:
    engines_to_try: Sequence[Optional[str]] = (
        [engine] if engine else ["netcdf4", "h5netcdf", "scipy", None]
    )
    errors: List[str] = []
    for eng in engines_to_try:
        try:
            ds = xr.open_dataset(path, engine=eng)
            _ = list(ds.dims.items())
            return ds
        except Exception as exc:
            errors.append(f"engine={eng!r}: {exc}")
    raise RuntimeError("Failed to open dataset with available engines:\n" + "\n".join(errors))


def guess_coord_names(ds: xr.Dataset) -> Tuple[Optional[str], Optional[str]]:
    lat_candidates = ["lat", "latitude", "LAT", "LSMLAT", "lsmlat", "y"]
    lon_candidates = ["lon", "longitude", "LON", "LSMLON", "lsmlon", "x"]
    lat_name = next((n for n in lat_candidates if n in ds.variables), None)
    lon_name = next((n for n in lon_candidates if n in ds.variables), None)
    if lat_name is None:
        lat_name = next((d for d in ds.dims if d.lower() in ("lat", "lsmlat", "y")), None)
    if lon_name is None:
        lon_name = next((d for d in ds.dims if d.lower() in ("lon", "lsmlon", "x")), None)
    return lat_name, lon_name


def coarsen_for_plot(da: xr.DataArray, factor: int) -> xr.DataArray:
    if factor <= 1:
        return da
    dims_sorted = sorted(da.sizes.items(), key=lambda kv: kv[1], reverse=True)
    dims_to_coarsen = [d for d, _ in dims_sorted[:2]]
    coarsen_kwargs = {d: factor for d in dims_to_coarsen if d in da.dims}
    try:
        return da.coarsen(**coarsen_kwargs, boundary="trim").mean()
    except Exception:
        return da


def select_time_slice(
    da: xr.DataArray,
    time_dim: Optional[str],
    time_index: Optional[int],
) -> xr.DataArray:
    if da.ndim <= 2:
        return da
    dim_candidates = ["time", "month", "t", "date", "year"]
    dim = None
    if time_dim and time_dim in da.dims:
        dim = time_dim
    else:
        for d in dim_candidates:
            if d in da.dims:
                dim = d
                break
    if dim is None:
        # Pick smallest non-spatial dim
        dims_sorted = sorted(da.sizes.items(), key=lambda kv: kv[1])
        dim = dims_sorted[0][0] if dims_sorted else None
    if dim is None or dim not in da.dims:
        return da
    idx = 0 if time_index is None else max(0, min(time_index, da.sizes[dim] - 1))
    try:
        return da.isel({dim: idx})
    except Exception:
        return da


def parse_levels(levels: Optional[List[float]]) -> Optional[List[float]]:
    if not levels:
        return None
    try:
        return [float(v) for v in levels]
    except Exception:
        return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Contour plotting for AvgTempColdMonth from surfdata NetCDF.")
    p.add_argument("--file", required=True, help="Path to surfdata NetCDF file")
    p.add_argument("--var", default="AvgTempColdMonth", help="Variable name to plot")
    p.add_argument("--engine", default=None, choices=[None, "netcdf4", "h5netcdf", "scipy"])
    p.add_argument("--temp-range", nargs=2, type=float, metavar=("MIN", "MAX"),
                   help="Temperature range (C) for filled contours")
    p.add_argument("--temp-level", nargs="+", type=float,
                   help="Specific temperature(s) (C) for contour lines")
    p.add_argument("--levels", nargs="+", type=float,
                   help="Explicit contour levels for filled contours (overrides --num-levels)")
    p.add_argument("--num-levels", type=int, default=10, help="Number of levels for range-based contours")
    p.add_argument("--time-dim", default=None, help="Time-like dimension name if variable is temporal")
    p.add_argument("--time-index", type=int, default=0, help="Time index to select if temporal")
    p.add_argument("--origin", choices=["auto", "upper", "lower"], default="auto",
                   help="Plot origin if using 1D lat/lon.")
    p.add_argument("--cmap", default="coolwarm", help="Colormap for filled contours")
    p.add_argument("--coarsen", type=int, default=1, help="Coarsening factor to reduce resolution")
    p.add_argument("--title", default=None, help="Override plot title")
    p.add_argument("--show", action="store_true", help="Show figure interactively")
    p.add_argument("--save", action="store_true", help="Save figure to --outdir")
    p.add_argument("--outdir", default="./contours", help="Output directory for saved figures")
    p.add_argument("--dpi", type=int, default=150, help="Figure DPI")
    p.add_argument("--figsize", nargs=2, type=float, metavar=("W", "H"), default=[8.5, 6.5],
                   help="Figure size in inches")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.show:
        import matplotlib
        matplotlib.use(matplotlib.get_backend())

    if not os.path.isfile(args.file):
        print(f"ERROR: file not found: {args.file}", file=sys.stderr)
        sys.exit(2)

    ds = try_open_dataset(args.file, args.engine)
    if args.var not in ds.data_vars:
        print(f"ERROR: variable not found: {args.var}", file=sys.stderr)
        print(f"Available variables: {', '.join(ds.data_vars)}", file=sys.stderr)
        sys.exit(2)

    da = ds[args.var]
    da = select_time_slice(da, args.time_dim, args.time_index)
    da = da.squeeze(drop=True)
    da = coarsen_for_plot(da, args.coarsen)

    lat_name, lon_name = guess_coord_names(ds)
    lat = da.coords.get(lat_name) if lat_name else None
    lon = da.coords.get(lon_name) if lon_name else None

    arr = da.values
    mask = ~np.isfinite(arr)
    for key in ("_FillValue", "missing_value", "fill_value"):
        if key in da.attrs:
            try:
                fv = float(da.attrs[key])
                mask |= (arr == fv)
            except Exception:
                pass
    masked = np.ma.array(arr, mask=mask)

    fig, ax = plt.subplots(figsize=tuple(args.figsize), dpi=args.dpi)

    # Prepare coordinate grids for contouring
    x, y = None, None
    if lat is not None and lon is not None:
        try:
            if lat.ndim == 1 and lon.ndim == 1:
                x, y = lon.values, lat.values
            elif lat.ndim == 2 and lon.ndim == 2:
                x, y = lon.values, lat.values
        except Exception:
            x, y = None, None

    # Filled contours for a range
    filled = None
    if args.temp_range:
        tmin, tmax = float(args.temp_range[0]), float(args.temp_range[1])
        if tmin > tmax:
            tmin, tmax = tmax, tmin
        levels = parse_levels(args.levels)
        if levels is None:
            levels = list(np.linspace(tmin, tmax, max(2, args.num_levels)))
        masked_range = np.ma.masked_outside(masked, tmin, tmax)
        if x is not None and y is not None:
            filled = ax.contourf(x, y, masked_range, levels=levels, cmap=args.cmap)
        else:
            filled = ax.contourf(masked_range, levels=levels, cmap=args.cmap)

    # Contour lines for specific temperatures
    if args.temp_level:
        levels = [float(v) for v in args.temp_level]
        if x is not None and y is not None:
            cs = ax.contour(x, y, masked, levels=levels, colors="k", linewidths=0.8)
        else:
            cs = ax.contour(masked, levels=levels, colors="k", linewidths=0.8)
        ax.clabel(cs, inline=True, fontsize=8, fmt="%g C")

    title = args.title or f"{args.var} contour"
    if args.temp_range:
        title += f" (range {args.temp_range[0]}..{args.temp_range[1]} C)"
    if args.temp_level:
        title += f" (levels {', '.join(str(v) for v in args.temp_level)} C)"
    ax.set_title(title)

    if lon is not None and lat is not None:
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

    if args.origin in ("upper", "lower"):
        ax.set_ylim(sorted(ax.get_ylim(), reverse=(args.origin == "upper")))

    if filled is not None:
        cbar = fig.colorbar(filled, ax=ax, shrink=0.8)
        cbar.set_label(da.attrs.get("units", ""))

    if args.save:
        os.makedirs(args.outdir, exist_ok=True)
        safe_var = args.var.replace("/", "_")
        fname = f"{safe_var}_contour.png"
        out_path = os.path.join(args.outdir, fname)
        fig.tight_layout()
        fig.savefig(out_path)
        print(f"Saved: {out_path}")

    if args.show:
        plt.show()
    else:
        plt.close(fig)


if __name__ == "__main__":
    main()
