#!/usr/bin/env python3
"""
Validate and visualize variables in a surfdata NetCDF file.

Usage examples:
  python3 NA_surfdataGEN/validate_visualize_surfdata.py \
    --file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc \
    --list

  python3 NA_surfdataGEN/validate_visualize_surfdata.py \
    --file /Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/dataProduct_DOI/Surfdata.Daymet_NA.1km.2d_VegMapLandUnit.c251202.nc \
    --vars PCT_PFT PCT_LANDUNIT LAKEFRAC \
    --validate --stats --plot --save --outdir ./surfdata_figs
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

try:
    import xarray as xr
except Exception as exc:  # pragma: no cover
    print(
        "ERROR: xarray is required. Install with:\n  pip install xarray netCDF4 h5netcdf matplotlib numpy",
        file=sys.stderr,
    )
    raise

try:
    import matplotlib
    matplotlib.use("Agg")  # non-interactive by default; enable with --show
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover
    print("ERROR: matplotlib is required. Install with:\n  pip install matplotlib", file=sys.stderr)
    raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and visualize variables in a surfdata NetCDF file."
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to surfdata NetCDF file",
    )
    parser.add_argument(
        "--engine",
        default=None,
        choices=[None, "netcdf4", "h5netcdf", "scipy"],
        help="xarray engine to use. If not set, will try multiple.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List variables and exit.",
    )
    parser.add_argument(
        "--vars",
        nargs="+",
        dest="vars_to_use",
        help="Variables to validate/plot. If omitted, will select likely key variables automatically.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation checks for selected variables.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print statistics (min/max/mean/NaN count) for selected variables.",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate map plots for selected variables.",
    )
    parser.add_argument(
        "--origin",
        choices=["auto", "upper", "lower"],
        default="upper",
        help="Image origin for plotting. 'upper' puts the first row at the top.",
    )
    parser.add_argument(
        "--nan-color",
        default="white",
        help="Matplotlib color for NaN (masked) pixels, e.g., 'white' or '#ffffff'.",
    )
    parser.add_argument(
        "--nan-alpha",
        type=float,
        default=0.0,
        help="Alpha for NaN (masked) pixels (0.0 transparent .. 1.0 opaque).",
    )
    parser.add_argument(
        "--category-mode",
        choices=["sum", "each", "index"],
        default="sum",
        help="How to handle small category dims (e.g., PFT, landunit) when plotting.",
    )
    parser.add_argument(
        "--category-index",
        type=int,
        default=0,
        help="Category index to plot when --category-mode=index.",
    )
    parser.add_argument(
        "--category-dim",
        default=None,
        help="Explicit category dimension name to use (e.g., pft, landunit). If not set, will auto-detect.",
    )
    parser.add_argument(
        "--weight-by",
        default=None,
        help="Variable name to weight by before plotting (e.g., PCT_NATVEG). If percentage-like, divides by 100.",
    )
    parser.add_argument(
        "--mask-by",
        default=None,
        help="Variable name to use as an explicit mask; any value <0 or NaN will be masked (useful for ocean masking).",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show figures interactively (uses default backend).",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save figures to --outdir instead of (or in addition to) showing them.",
    )
    parser.add_argument(
        "--outdir",
        default="./figs",
        help="Output directory to save plots if --save is given.",
    )
    parser.add_argument(
        "--coarsen",
        type=int,
        default=1,
        help="Coarsening factor for plotting to reduce resolution (e.g., 2, 4, 8).",
    )
    return parser.parse_args()


def try_open_dataset(path: str, engine: Optional[str]) -> xr.Dataset:
    """
    Open the NetCDF via xarray. If engine is None, try multiple engines robustly.
    """
    engines_to_try: Sequence[Optional[str]] = (
        [engine] if engine else ["netcdf4", "h5netcdf", "scipy", None]
    )
    errors: List[str] = []
    for eng in engines_to_try:
        try:
            ds = xr.open_dataset(path, engine=eng)
            # Touch something to force a small read and validate
            _ = list(ds.dims.items())
            return ds
        except Exception as exc:  # pragma: no cover
            errors.append(f"engine={eng!r}: {exc}")
    raise RuntimeError(
        "Failed to open dataset with available engines:\n" + "\n".join(errors)
    )


def guess_coord_names(ds: xr.Dataset) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempt to guess latitude/longitude coordinate variable names.
    """
    lat_candidates = ["lat", "latitude", "LAT", "LSMLAT", "lsmlat", "y"]
    lon_candidates = ["lon", "longitude", "LON", "LSMLON", "lsmlon", "x"]

    lat_name = next((n for n in lat_candidates if n in ds.variables), None)
    lon_name = next((n for n in lon_candidates if n in ds.variables), None)

    # Sometimes lat/lon are coords (dims) not data_vars
    if lat_name is None:
        lat_name = next((d for d in ds.dims if d.lower() in ("lat", "lsmlat", "y")), None)
    if lon_name is None:
        lon_name = next((d for d in ds.dims if d.lower() in ("lon", "lsmlon", "x")), None)

    return lat_name, lon_name


def select_default_variables(ds: xr.Dataset) -> List[str]:
    """
    Heuristic selection of variables likely relevant for veg/landunit surfdata.
    """
    preferred_keywords = [
        "PCT_PFT",
        "PCT_LANDUNIT",
        "LAKEFRAC",
        "URBAN",
        "GLACIER",
        "WETLAND",
        "PCT_",
        "_percentage",
        "TEMP",
        "LAND_FRACTION",
    ]
    vars_in_ds = list(ds.data_vars)
    selected: List[str] = []
    for v in vars_in_ds:
        if any(k.lower() in v.lower() for k in preferred_keywords):
            selected.append(v)
    if not selected:
        # Fallback: pick first few non-coordinate variables
        selected = vars_in_ds[:6]
    return selected


def summarize_variable(da: xr.DataArray) -> str:
    """
    Compute simple stats summary for a data array.
    """
    arr = da.values
    finite = np.isfinite(arr)
    nan_count = np.size(arr) - np.count_nonzero(finite)
    if np.any(finite):
        vmin = np.nanmin(arr)
        vmax = np.nanmax(arr)
        vmean = np.nanmean(arr)
        return f"min={vmin:.6g}, max={vmax:.6g}, mean={vmean:.6g}, NaNs={nan_count}"
    return f"All values NaN (total NaNs={nan_count})"


def is_percentage_like(name: str, da: xr.DataArray) -> bool:
    """
    Heuristic check if a variable represents percentages.
    """
    name_lower = name.lower()
    if "pct" in name_lower or "percentage" in name_lower or "%" in name_lower:
        return True
    units = str(da.attrs.get("units", "")).lower()
    if units in ("percent", "%"):
        return True
    return False


def find_small_category_dim(da: xr.DataArray) -> Optional[str]:
    """
    Find a likely category dimension (e.g., pft, landunit) by small cardinality.
    """
    for d in da.dims:
        if da.sizes[d] <= 30 and d.lower() in ("pft", "landunit", "category", "lu", "vegtype"):
            return d
    # Generic small dim heuristic
    for d in da.dims:
        if da.sizes[d] <= 30 and da.ndim >= 3:
            return d
    return None


def validate_variable(name: str, da: xr.DataArray) -> List[str]:
    """
    Run validation checks; return list of warnings/errors discovered.
    """
    issues: List[str] = []
    arr = da.values

    # NaN check
    num_nan = np.isnan(arr).sum()
    if num_nan > 0:
        issues.append(f"{name}: contains {int(num_nan)} NaN values")

    # Percentage-like checks
    if is_percentage_like(name, da):
        # Check plausible bounds
        finite = np.isfinite(arr)
        if np.any(finite):
            min_v = np.nanmin(arr)
            max_v = np.nanmax(arr)
            if min_v < -1e-3 or max_v > 100.0 + 1e-3:
                issues.append(
                    f"{name}: percentage-like variable has values outside [0,100]: "
                    f"min={min_v:.3g}, max={max_v:.3g}"
                )
        # Check across-category sum if applicable
        cat_dim = find_small_category_dim(da)
        if cat_dim:
            summed = da.sum(dim=cat_dim, skipna=True)
            # Allow tolerance; sometimes not exactly 100 due to rounding
            diff = np.abs(summed - 100.0)
            too_far = (diff > 1.0) & np.isfinite(diff)
            if bool(too_far.any()):
                frac_bad = float(too_far.sum() / np.size(diff))
                issues.append(
                    f"{name}: sum across '{cat_dim}' deviates from 100 by >1.0 at "
                    f"{frac_bad:.2%} of locations"
                )

    # Fraction-like variables (0..1) by units
    units = str(da.attrs.get("units", "")).lower()
    if units in ("fraction", "1", "unitless"):
        finite = np.isfinite(arr)
        if np.any(finite):
            min_v = np.nanmin(arr)
            max_v = np.nanmax(arr)
            if min_v < -1e-6 or max_v > 1.0 + 1e-6:
                issues.append(
                    f"{name}: fraction-like variable has values outside [0,1]: "
                    f"min={min_v:.3g}, max={max_v:.3g}"
                )

    return issues


def prepare_plot_slices(
    name: str,
    da: xr.DataArray,
    ds: xr.Dataset,
    category_dim: Optional[str],
    category_mode: str,
    category_index: int,
    weight_by: Optional[str],
) -> List[Tuple[str, xr.DataArray]]:
    """
    Prepare one or multiple 2D slices for plotting based on category handling and weighting.
    Returns list of (suffix_name, dataarray).
    """
    # Optional weighting
    data = da
    if weight_by and weight_by in ds.data_vars:
        wb = ds[weight_by]
        try:
            scale = 100.0 if is_percentage_like(weight_by, wb) else 1.0
        except Exception:
            scale = 1.0
        try:
            data = data * (wb / scale)
        except Exception:
            try:
                data, wb_aligned = xr.align(data, wb, join="inner")
                data = data * (wb_aligned / scale)
            except Exception:
                pass

    # Category handling
    cat_dim = category_dim or find_small_category_dim(data)
    outputs: List[Tuple[str, xr.DataArray]] = []
    if not cat_dim or data.ndim <= 2:
        outputs.append((name, data))
        return outputs

    if category_mode == "sum":
        try:
            summed = data.sum(dim=cat_dim, skipna=True)
            outputs.append((name, summed))
        except Exception:
            outputs.append((name, data))
    elif category_mode == "index":
        idx = max(0, min(category_index, data.sizes[cat_dim] - 1))
        try:
            sel = data.isel({cat_dim: idx})
            outputs.append((f"{name}_{cat_dim}{idx}", sel))
        except Exception:
            outputs.append((name, data))
    elif category_mode == "each":
        try:
            for i in range(data.sizes[cat_dim]):
                sel = data.isel({cat_dim: i})
                outputs.append((f"{name}_{cat_dim}{i}", sel))
        except Exception:
            outputs.append((name, data))
    else:
        outputs.append((name, data))

    return outputs


def coarsen_for_plot(da: xr.DataArray, factor: int) -> xr.DataArray:
    if factor <= 1:
        return da
    # Identify the two largest spatial dims to coarsen
    dims_sorted = sorted(da.sizes.items(), key=lambda kv: kv[1], reverse=True)
    dims_to_coarsen = [d for d, _ in dims_sorted[:2]]
    coarsen_kwargs = {d: factor for d in dims_to_coarsen if d in da.dims}
    try:
        return da.coarsen(**coarsen_kwargs, boundary="trim").mean()
    except Exception:
        return da


def plot_variable(
    name: str,
    da: xr.DataArray,
    lat_name: Optional[str],
    lon_name: Optional[str],
    origin_mode: str,
    nan_color: str,
    nan_alpha: float,
    mask_by: Optional["xr.DataArray"],
    outdir: str,
    save: bool,
    show: bool,
) -> None:
    """
    Plot a 2D slice (or aggregated slice) using imshow.
    Category reduction (sum/each/index) is handled earlier in prepare_plot_slices.
    """
    data = da

    # If more than 2 dims remain, try to squeeze/select a single index on small dims
    while data.ndim > 2:
        # Pick a dim with smallest size > 1
        sizes = [(d, data.sizes[d]) for d in data.dims]
        sizes = [s for s in sizes if s[1] > 1]
        if not sizes:
            data = data.squeeze()
            break
        dim_to_index = sorted(sizes, key=lambda kv: kv[1])[0][0]
        data = data.isel({dim_to_index: 0})

    # Compute extent if lat/lon are 1D coords aligned to dims
    extent = None
    origin = "upper" if origin_mode == "upper" else "lower"
    if lat_name and lon_name:
        try:
            lat = data.coords.get(lat_name, None)
            lon = data.coords.get(lon_name, None)
            if lat is not None and lon is not None:
                # Handle 1D or 2D coords
                if lat.ndim == 1 and lon.ndim == 1:
                    # Decide origin if auto
                    if origin_mode == "auto":
                        lat_vals = lat.values
                        if lat_vals.size >= 2 and lat_vals[0] > lat_vals[-1]:
                            origin = "upper"
                        else:
                            origin = "lower"
                    extent = [float(lon.min()), float(lon.max()), float(lat.min()), float(lat.max())]
                elif lat.ndim == 2 and lon.ndim == 2:
                    if origin_mode == "auto":
                        # For 2D, compare mean latitude of first vs last row
                        lat_vals = lat.values
                        if lat_vals.shape[0] >= 2:
                            top_mean = float(np.nanmean(lat_vals[0, :]))
                            bottom_mean = float(np.nanmean(lat_vals[-1, :]))
                            origin = "upper" if top_mean > bottom_mean else "lower"
                    extent = [
                        float(np.nanmin(lon.values)),
                        float(np.nanmax(lon.values)),
                        float(np.nanmin(lat.values)),
                        float(np.nanmax(lat.values)),
                    ]
        except Exception:
            extent = None

    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    # Mask NaNs and attribute-declared fill values; set color for masked values
    cmap = plt.cm.viridis.copy()
    try:
        cmap.set_bad(color=nan_color, alpha=nan_alpha)
    except Exception:
        # Fallback without customization
        pass
    # Align optional mask_by to data
    if mask_by is not None:
        try:
            # Drop any singleton dims like 'file'=1 to match 2D slices
            try:
                mask_by = mask_by.squeeze(drop=True)
            except Exception:
                pass
            data, mask_by = xr.align(data, mask_by, join="inner")
        except Exception:
            pass
    arr = data.values
    mask = ~np.isfinite(arr)
    # Respect common fill-value attributes if present
    for key in ("_FillValue", "missing_value", "fill_value"):
        if key in data.attrs:
            try:
                fv = float(data.attrs[key])
                mask |= (arr == fv)
            except Exception:
                pass
    # Heuristic: many count grids use negative values as nodata
    if np.issubdtype(arr.dtype, np.integer):
        mask |= (arr < 0)
    # Apply external mask (e.g., pft_total_count < 0 → ocean)
    if mask_by is not None:
        mb = mask_by.values
        mask |= (~np.isfinite(mb)) | (mb < 0)
    masked = np.ma.array(arr, mask=mask)
    im = ax.imshow(
        masked,
        origin=origin,
        interpolation="nearest",
        extent=extent,
        aspect="auto",
        cmap=cmap,
    )
    ax.set_title(name)
    if extent:
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
    else:
        ax.set_xlabel(data.dims[-1] if data.ndim >= 1 else "")
        ax.set_ylabel(data.dims[-2] if data.ndim >= 2 else "")
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label(data.attrs.get("units", ""))

    if save:
        os.makedirs(outdir, exist_ok=True)
        out_path = os.path.join(outdir, f"{name}.png")
        fig.tight_layout()
        fig.savefig(out_path)
        print(f"[plot] Saved {out_path}")
        plt.close(fig)
    if show:
        plt.show()


def main() -> None:
    args = parse_args()
    if args.show:
        # Switch backend when interactive display requested
        import matplotlib
        matplotlib.use(matplotlib.get_backend())

    if not os.path.isfile(args.file):
        print(f"ERROR: file not found: {args.file}", file=sys.stderr)
        sys.exit(2)

    print(f"Opening: {args.file}")
    ds = try_open_dataset(args.file, args.engine)
    print("Opened dataset")

    if args.list:
        print("\nDimensions:")
        for k, v in ds.dims.items():
            print(f"  - {k}: {v}")
        print("\nVariables:")
        for v in ds.data_vars:
            da = ds[v]
            shape_str = "x".join(str(da.sizes[d]) for d in da.dims)
            print(f"  - {v}  dims=({', '.join(da.dims)})  shape={shape_str}  units={da.attrs.get('units', '')}")
        return

    lat_name, lon_name = guess_coord_names(ds)

    variables: List[str]
    if args.vars_to_use:
        variables = [v for v in args.vars_to_use if v in ds.data_vars]
        missing = set(args.vars_to_use) - set(variables)
        for m in sorted(missing):
            print(f"WARNING: variable not found and will be skipped: {m}", file=sys.stderr)
    else:
        variables = select_default_variables(ds)
        print("Auto-selected variables:", ", ".join(variables))

    if not variables:
        print("No variables to process. Use --list to inspect names, then pass with --vars ...", file=sys.stderr)
        sys.exit(1)

    # Process variables
    any_plotted = False
    mask_da_global = None
    if hasattr(args, "mask_by") and args.mask_by and args.mask_by in ds.data_vars:
        mask_da_global = ds[args.mask_by]
    for name in variables:
        da = ds[name]
        # Prepare plot slices based on category handling and optional weighting
        slices = prepare_plot_slices(
            name=name,
            da=da,
            ds=ds,
            category_dim=args.category_dim,
            category_mode=args.category_mode,
            category_index=args.category_index,
            weight_by=args.weight_by,
        )

        if args.stats:
            print(f"[stats] {name}: {summarize_variable(da)}")

        if args.validate:
            issues = validate_variable(name, da)
            if issues:
                for msg in issues:
                    print(f"[check] {msg}")
            else:
                print(f"[check] {name}: OK")

        if args.plot:
            for out_name, da_slice in slices:
                # Coarsen for plotting if requested (applies to plotting only)
                da_for_plot = coarsen_for_plot(da_slice, args.coarsen)
                try:
                    plot_variable(
                        name=out_name,
                        da=da_for_plot,
                        lat_name=lat_name,
                        lon_name=lon_name,
                        origin_mode=args.origin,
                        nan_color=args.nan_color,
                        nan_alpha=args.nan_alpha,
                        mask_by=mask_da_global,
                        outdir=args.outdir,
                        save=args.save,
                        show=args.show,
                    )
                    any_plotted = True
                except Exception as exc:
                    print(f"[plot] {out_name}: failed to plot ({exc})", file=sys.stderr)

    if args.plot and args.show and not any_plotted:
        print("No plots were generated.", file=sys.stderr)


if __name__ == "__main__":
    main()


