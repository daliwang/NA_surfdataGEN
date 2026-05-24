#!/usr/bin/env python3
"""Compare E3SM historical land-use (2015) vs NALCMS surfdata on the Daymet grid."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from compare_lulc_vs_nalcms_2020_vars import (
    compute_stride_for_plot,
    downsample_array,
    get_lat_lon_from_ds,
    get_plot_grid_from_ds,
    get_xy_grid_from_ds,
    make_cmap,
    nearest_regrid_to_target,
    prepare_paper_imshow,
    style_paper_map_axes,
)


def load_dataset(path: Path) -> xr.Dataset:
    return xr.open_dataset(path)


def get_total_urban(da: xr.DataArray) -> np.ndarray:
    if "numurbl" in da.dims:
        return da.sum("numurbl").astype(np.float64).values
    return da.astype(np.float64).values


def save_triple_panel(
    var_label: str,
    e3sm_or: np.ndarray,
    nalcms_or: np.ndarray,
    diff_or: np.ndarray,
    mask_or: np.ndarray,
    vmin: float,
    vmax: float,
    dlim: float,
    extent,
    origin: str,
    outdir: Path,
    file_stem: Optional[str] = None,
    ref_label: str = "E3SM 2015",
) -> None:
    stem = file_stem or var_label.lower()
    panel_file = outdir / f"{stem}_e3sm2015_vs_nalcms_panel.png"
    e3sm_masked = np.where(mask_or, e3sm_or, np.nan)
    nalcms_masked = np.where(mask_or, nalcms_or, np.nan)
    diff_masked = np.where(mask_or, diff_or, np.nan)

    fig, axes = plt.subplots(1, 3, figsize=(18, 7.5))
    fig.subplots_adjust(left=0.04, right=0.96, top=0.90, bottom=0.12, wspace=0.32)
    cmap = make_cmap("viridis")
    diff_cmap = make_cmap("coolwarm")

    for ax in axes:
        ax.set_facecolor("white")

    im_map = axes[0].imshow(
        np.ma.masked_invalid(nalcms_masked),
        origin=origin,
        extent=extent,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest",
        aspect="equal",
    )
    axes[0].set_title(f"NALCMS {var_label}", pad=10)
    style_paper_map_axes(axes[0])

    axes[1].imshow(
        np.ma.masked_invalid(e3sm_masked),
        origin=origin,
        extent=extent,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest",
        aspect="equal",
    )
    axes[1].set_title(f"{ref_label} {var_label}", pad=10)
    style_paper_map_axes(axes[1])

    im_diff = axes[2].imshow(
        np.ma.masked_invalid(diff_masked),
        origin=origin,
        extent=extent,
        cmap=diff_cmap,
        vmin=-dlim,
        vmax=dlim,
        interpolation="nearest",
        aspect="equal",
    )
    axes[2].set_title(f"NALCMS - {ref_label}", pad=10)
    style_paper_map_axes(axes[2])

    cbar_map = fig.colorbar(im_map, ax=axes[:2], shrink=0.88, pad=0.04, fraction=0.046)
    cbar_map.set_label(var_label)
    cbar_diff = fig.colorbar(im_diff, ax=axes[2], shrink=0.88, pad=0.04, fraction=0.046)
    cbar_diff.set_label("Difference")
    fig.savefig(panel_file, dpi=200, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    print(f"Wrote {panel_file}")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    default_e3sm = repo_root / "comparison" / "landuse.PCT_subset_last.nc"
    default_nalcms = (
        repo_root / "surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc"
    )
    default_outdir = repo_root.parent / "PaperFigures" / "comparison" / "e3sm_landuse_2015"

    parser = argparse.ArgumentParser(
        description="Compare E3SM historical land-use 2015 vs NALCMS surfdata (triple panel)."
    )
    parser.add_argument("--e3sm-file", type=Path, default=default_e3sm)
    parser.add_argument("--nalcms-file", type=Path, default=default_nalcms)
    parser.add_argument("--outdir", type=Path, default=default_outdir)
    parser.add_argument(
        "--vars",
        nargs="+",
        default=["PCT_LAKE", "PCT_NATVEG", "PCT_GLACIER", "PCT_URBAN"],
    )
    parser.add_argument("--scale", choices=["robust", "fixed"], default="fixed")
    parser.add_argument("--map-min", type=float, default=0.0)
    parser.add_argument("--map-max", type=float, default=100.0)
    parser.add_argument("--diff-lim", type=float, default=100.0)
    parser.add_argument("--max-points", type=int, default=1_000_000)
    parser.add_argument(
        "--ref-label",
        default="E3SM 2015",
        help="Label for the reference product in panel titles.",
    )
    args = parser.parse_args()

    if not args.e3sm_file.is_file():
        raise SystemExit(f"E3SM land-use file not found: {args.e3sm_file}")
    if not args.nalcms_file.is_file():
        raise SystemExit(f"NALCMS surfdata file not found: {args.nalcms_file}")

    args.outdir.mkdir(parents=True, exist_ok=True)

    dsE = load_dataset(args.e3sm_file)
    dsN = load_dataset(args.nalcms_file)
    latE, lonE = get_lat_lon_from_ds(dsE)
    latN, lonN = get_lat_lon_from_ds(dsN)
    xN_grid, yN_grid, _kindN = get_plot_grid_from_ds(dsN, "xy")
    x_1d = np.asarray(dsN.coords["x"].values if "x" in dsN.coords else dsN["x"].values, dtype=float)
    y_1d = np.asarray(dsN.coords["y"].values if "y" in dsN.coords else dsN["y"].values, dtype=float)

    for var in args.vars:
        if var not in dsE.data_vars:
            print(f"Skipping {var}: not found in E3SM dataset.")
            continue
        if var not in dsN.data_vars:
            print(f"Skipping {var}: not found in NALCMS dataset.")
            continue

        if var == "PCT_URBAN":
            e3sm_data = get_total_urban(dsE[var])
            nalcms_data = get_total_urban(dsN[var])
        else:
            e3sm_data = dsE[var].astype(np.float64).values
            nalcms_data = dsN[var].astype(np.float64).values

        e3sm_on_n = nearest_regrid_to_target(latE, lonE, e3sm_data, latN, lonN)
        e3sm_plot = downsample_array(e3sm_on_n, max_points=args.max_points)
        nalcms_plot = downsample_array(nalcms_data, max_points=args.max_points)

        stride = compute_stride_for_plot(
            nalcms_data.shape[0], nalcms_data.shape[1], max_points=args.max_points
        )
        lonN_ds = lonN[::stride, ::stride]
        latN_ds = latN[::stride, ::stride]
        maskN = np.isfinite(lonN_ds) & np.isfinite(latN_ds)

        if args.scale == "robust":
            vals = np.concatenate([e3sm_plot.ravel(), nalcms_plot.ravel()])
            vmin = float(np.nanpercentile(vals, 2))
            vmax = float(np.nanpercentile(vals, 98))
        else:
            vmin, vmax = args.map_min, args.map_max

        diff_plot = nalcms_plot - e3sm_plot
        if args.scale == "robust":
            dlim = float(np.nanpercentile(np.abs(diff_plot.ravel()), 98))
        else:
            dlim = float(args.diff_lim)

        e3sm_or, extent, origin = prepare_paper_imshow(e3sm_plot, x_1d, y_1d)
        nalcms_or, _, _ = prepare_paper_imshow(nalcms_plot, x_1d, y_1d)
        diff_or, _, _ = prepare_paper_imshow(diff_plot, x_1d, y_1d)
        mask_or, _, _ = prepare_paper_imshow(maskN.astype(float), x_1d, y_1d)
        mask_or = mask_or > 0.5

        save_triple_panel(
            var_label=var,
            e3sm_or=e3sm_or,
            nalcms_or=nalcms_or,
            diff_or=diff_or,
            mask_or=mask_or,
            vmin=vmin,
            vmax=vmax,
            dlim=dlim,
            extent=extent,
            origin=origin,
            outdir=args.outdir,
            file_stem=var.lower(),
            ref_label=args.ref_label,
        )

    dsE.close()
    dsN.close()


if __name__ == "__main__":
    main()
