import os
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree
import argparse


def normalize_longitude(lon_array: np.ndarray) -> np.ndarray:
    lon = np.asarray(lon_array)
    # Map longitudes to [0, 360) to match typical surfdata LONGXY
    lon_norm = np.mod(lon, 360.0)
    return lon_norm


def get_total_urban(da):
    # Sum over numurbl if present, otherwise return as-is
    if "numurbl" in da.dims:
        return da.sum("numurbl")
    return da


def get_urban_layers(da):
    # Return list of up to 3 layers for PCT_URBAN if numurbl exists, else singleton list
    if "numurbl" in da.dims:
        layers = []
        for i in range(min(3, da.sizes.get("numurbl", 0))):
            layers.append(da.isel(numurbl=i))
        # If fewer than 3, pad with zeros
        while len(layers) < 3:
            layers.append(xr.zeros_like(da.isel(numurbl=0)))
        return layers[:3]
    else:
        return [da]


def load_dataset(path: Path) -> xr.Dataset:
    return xr.open_dataset(path)


def get_lat_lon_from_ds(ds: xr.Dataset):
    # Prefer LATIXY/LONGXY if present, otherwise try common fallbacks
    lat_candidates = ["LATIXY", "lat", "latitude", "LAT"]
    lon_candidates = ["LONGXY", "LONG", "lon", "longitude", "LON"]
    lat_da = None
    lon_da = None
    for name in lat_candidates:
        if name in ds.variables:
            lat_da = ds[name]
            break
        if name in ds.coords:
            lat_da = ds.coords[name]
            break
    for name in lon_candidates:
        if name in ds.variables:
            lon_da = ds[name]
            break
        if name in ds.coords:
            lon_da = ds.coords[name]
            break
    if lat_da is None or lon_da is None:
        raise ValueError("Could not find latitude/longitude variables in dataset.")
    return lat_da.values, lon_da.values


def get_xy_grid_from_ds(ds: xr.Dataset):
    """
    Return 2D x/y grids for plotting if available.
    Accepts either 1D x/y coords (creates meshgrid) or existing 2D x/y variables.
    """
    x_da = None
    y_da = None
    # Prefer coords over variables
    for name in ["x", "X", "xc", "XC"]:
        if name in ds.coords:
            x_da = ds.coords[name]
            break
        if name in ds.variables:
            x_da = ds[name]
            break
    for name in ["y", "Y", "yc", "YC"]:
        if name in ds.coords:
            y_da = ds.coords[name]
            break
        if name in ds.variables:
            y_da = ds[name]
            break
    # Fallback: some files store projected axes in lon/lat 1D coords
    if x_da is None or y_da is None:
        lon_1d = ds.coords.get("lon", ds.variables.get("lon"))
        lat_1d = ds.coords.get("lat", ds.variables.get("lat"))
        if lon_1d is not None and lat_1d is not None:
            try:
                if lon_1d.ndim == 1 and lat_1d.ndim == 1:
                    x_da = lon_1d
                    y_da = lat_1d
            except Exception:
                pass
    if x_da is None or y_da is None:
        return None, None
    x_val = np.asarray(x_da.values)
    y_val = np.asarray(y_da.values)
    if x_val.ndim == 1 and y_val.ndim == 1:
        # Create a 2D grid in the natural plotting order (rows: y, cols: x)
        xg, yg = np.meshgrid(x_val, y_val, indexing="xy")
        return xg, yg
    if x_val.ndim == 2 and y_val.ndim == 2:
        return x_val, y_val
    # Mixed dimensionality (fallback: try to meshgrid if one is 1D)
    if x_val.ndim == 1 and y_val.ndim == 2 and y_val.shape[1] == x_val.size:
        xg = np.tile(x_val[np.newaxis, :], (y_val.shape[0], 1))
        return xg, y_val
    if y_val.ndim == 1 and x_val.ndim == 2 and x_val.shape[0] == y_val.size:
        yg = np.tile(y_val[:, np.newaxis], (1, x_val.shape[1]))
        return x_val, yg
    return None, None


def get_plot_grid_from_ds(ds: xr.Dataset, mode: str):
    """
    Determine plotting grid and its kind:
    - If mode == 'xy': use x/y if available, else fall back to lon/lat.
    - If mode == 'lonlat': use lon/lat.
    - If mode == 'auto': prefer x/y if available, else lon/lat.
    Returns (X2D, Y2D, kind) where kind in {'xy', 'lonlat'}.
    """
    if mode in ("xy", "auto"):
        xg, yg = get_xy_grid_from_ds(ds)
        if xg is not None and yg is not None:
            return xg, yg, "xy"
        if mode == "xy":
            # Fall back if forced xy not available
            lat, lon = get_lat_lon_from_ds(ds)
            return lon, lat, "lonlat"
    # lon/lat path
    lat, lon = get_lat_lon_from_ds(ds)
    return lon, lat, "lonlat"


def nearest_regrid_to_target(lat_src, lon_src, data_src, lat_tgt, lon_tgt):
    """
    Regrid data_src(lat_src, lon_src) to the target grid lat_tgt/lon_tgt
    using nearest neighbor in lat/lon space via KDTree.
    """
    # Flatten and mask NaNs from source
    mask_src = np.isfinite(lat_src) & np.isfinite(lon_src) & np.isfinite(data_src)
    lat_src_f = lat_src[mask_src]
    lon_src_f = lon_src[mask_src]
    data_src_f = data_src[mask_src]

    # Normalize longitudes to [0, 360)
    lon_src_f = normalize_longitude(lon_src_f)
    lon_tgt_f = normalize_longitude(lon_tgt)

    # Build KDTree on (lat, lon)
    pts_src = np.column_stack((lat_src_f.ravel(), lon_src_f.ravel()))
    tree = cKDTree(pts_src)

    # Query for all target points
    tgt_shape = lat_tgt.shape
    lat_tgt_flat = lat_tgt.ravel()
    lon_tgt_flat = lon_tgt_f.ravel()
    valid_tgt = np.isfinite(lat_tgt_flat) & np.isfinite(lon_tgt_flat)

    regrid_flat = np.full(lat_tgt_flat.shape, np.nan, dtype=data_src_f.dtype)
    idxs = np.where(valid_tgt)[0]
    if idxs.size > 0:
        dists, nn = tree.query(np.column_stack((lat_tgt_flat[idxs], lon_tgt_flat[idxs])), k=1)
        regrid_flat[idxs] = data_src_f[nn]

    regrid = regrid_flat.reshape(tgt_shape)
    return regrid


def downsample_for_plot(x, y, z, max_points=1_000_000):
    """
    Downsample grid for plotting to avoid excessive memory/slow rendering.
    Keeps a stride so that total cells <= max_points.
    """
    ny, nx = z.shape
    stride = 1
    if nx * ny > max_points:
        stride_x = max(1, int(np.ceil(np.sqrt((nx * ny) / max_points))))
        stride_y = stride_x
    else:
        stride_x = stride_y = 1
    return x[::stride_y, ::stride_x], y[::stride_y, ::stride_x], z[::stride_y, ::stride_x]


def prepare_imshow(z, x_grid, y_grid):
    """
    Prepare array and parameters for imshow:
    - Flip left/right if x decreases from left to right
    - Choose origin='upper' if y decreases from top row to bottom row
    - Compute extent from x/y
    """
    xg = x_grid
    yg = y_grid
    z_plot = z
    # Horizontal orientation (left to right)
    try:
        x_left = np.nanmean(xg[:, 0])
        x_right = np.nanmean(xg[:, -1])
        if np.isfinite(x_left) and np.isfinite(x_right) and x_left > x_right:
            z_plot = np.fliplr(z_plot)
            xg = np.fliplr(xg)
    except Exception:
        pass
    # Vertical orientation (top to bottom)
    origin = "lower"
    try:
        y_top = np.nanmean(yg[0, :])
        y_bottom = np.nanmean(yg[-1, :])
        if np.isfinite(y_top) and np.isfinite(y_bottom) and y_top > y_bottom:
            origin = "upper"
    except Exception:
        origin = "lower"
    # Extent
    extent = [float(np.nanmin(xg)), float(np.nanmax(xg)), float(np.nanmin(yg)), float(np.nanmax(yg))]
    return z_plot, extent, origin

def make_cmap(name: str):
    cmap = plt.get_cmap(name).copy()
    # Make NaNs transparent (not plotted)
    cmap.set_bad(color=(0.0, 0.0, 0.0, 0.0))
    return cmap


def main():
    parser = argparse.ArgumentParser(description="Compare variables across three surfdata datasets.")
    parser.add_argument("--scale", choices=["robust", "fixed"], default="robust",
                        help="Color scaling mode for maps and per-layer figures. 'robust' uses 2nd/98th percentiles; 'fixed' uses provided limits.")
    parser.add_argument("--map-min", type=float, default=0.0,
                        help="Fixed vmin for maps/layers when --scale=fixed.")
    parser.add_argument("--map-max", type=float, default=100.0,
                        help="Fixed vmax for maps/layers when --scale=fixed.")
    parser.add_argument("--diff-lim", type=float, default=100.0,
                        help="Fixed absolute limit for difference plots when --scale=fixed (range will be [-diff-lim, +diff-lim]).")
    parser.add_argument("--vars", type=str, nargs="*", default=["PCT_URBAN", "PCT_LAKE", "PCT_GLACIER", "PCT_NATVEG", "PCT_NAT_PFT"],
                        help="Variables to compare. For PCT_NAT_PFT, plots per natpft layer.")
    parser.add_argument("--pft-start", type=int, default=None,
                        help="Start index (inclusive) for natpft layers when plotting PCT_NAT_PFT. Default: 0.")
    parser.add_argument("--pft-end", type=int, default=None,
                        help="End index (inclusive) for natpft layers when plotting PCT_NAT_PFT. Default: last.")
    parser.add_argument("--plot-coords", choices=["auto", "xy", "lonlat"], default="auto",
                        help="Which coordinates to use for plotting: 'xy' (projected), 'lonlat', or 'auto' (prefer 'xy' if available).")
    args = parser.parse_args()

    comparison_dir = Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison")
    dataset_global = comparison_dir / "surfdata_0.5x0.5_simyr1850_c200609_with_TOP.subset.nc"
    dataset_daymet_1km = comparison_dir / "surfdata.Daymet_NA.1km.2d.c250625.subset.nc"
    dataset_nalcms = Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c251230.nc")

    out_maps = comparison_dir / "pct_urban_maps.png"
    out_diffs = comparison_dir / "pct_urban_diffs.png"
    out_stats = comparison_dir / "pct_urban_stats.txt"

    dsA = load_dataset(dataset_global)       # Global 0.5°
    dsB = load_dataset(dataset_daymet_1km)   # 1 km 2D (Daymet)
    dsC = load_dataset(dataset_nalcms)       # 1 km 2D (NALCMS-derived)

    # Get lat/lon for each dataset
    latA, lonA = get_lat_lon_from_ds(dsA)
    latB, lonB = get_lat_lon_from_ds(dsB)
    latC, lonC = get_lat_lon_from_ds(dsC)

    # Determine plotting grids for B and C (prefer x/y when available or requested)
    xB_grid, yB_grid, kindB = get_plot_grid_from_ds(dsB, args.plot_coords)
    xC_grid, yC_grid, kindC = get_plot_grid_from_ds(dsC, args.plot_coords)

    # Helpers for generic variable processing
    def compute_stats_and_plots(var_name: str, daA: xr.DataArray, daB: xr.DataArray, daC: xr.DataArray,
                                suffix: str = "", per_layer_label: str | None = None,
                                vmin_override: float | None = None, vmax_override: float | None = None,
                                diff_lim_override: float | None = None,
                                xB_plot_grid: np.ndarray | None = None, yB_plot_grid: np.ndarray | None = None,
                                xC_plot_grid: np.ndarray | None = None, yC_plot_grid: np.ndarray | None = None,
                                kindB_override: str | None = None, kindC_override: str | None = None):
        # Regrid A -> B grid
        A_on_B = nearest_regrid_to_target(latA, lonA, daA.values, latB, lonB)
        # Masks
        valid_B = np.isfinite(daB.values)
        valid_C = np.isfinite(daC.values)
        valid_AonB = np.isfinite(A_on_B)
        common_B = valid_B & valid_AonB
        common_C = valid_C & valid_AonB
        common_BC = valid_B & valid_C
        # Stats
        def stats(a, b, mask):
            if mask.sum() == 0:
                return {"count": 0, "mean_a": np.nan, "mean_b": np.nan, "rmse": np.nan, "corr": np.nan}
            va = a[mask].ravel()
            vb = b[mask].ravel()
            diff = vb - va
            rmse = float(np.sqrt(np.nanmean(diff ** 2)))
            corr = float(np.corrcoef(va, vb)[0, 1]) if va.size > 1 else np.nan
            return {
                "count": int(va.size),
                "mean_a": float(np.nanmean(va)),
                "mean_b": float(np.nanmean(vb)),
                "rmse": rmse,
                "corr": corr,
            }
        stats_B_minus_A = stats(A_on_B, daB.values, common_B)
        stats_C_minus_A = stats(A_on_B, daC.values, common_C)
        stats_C_minus_B = stats(daB.values, daC.values, common_BC)
        # Save stats
        stat_file = comparison_dir / f"{var_name.lower()}{suffix}_stats.txt"
        with open(stat_file, "w") as f:
            title = f"{var_name} comparison"
            if per_layer_label is not None:
                title += f" ({per_layer_label})"
            f.write(f"{title} stats (units as in inputs):\n")
            f.write("B (Daymet 1km) vs A (Global 0.5° regridded to 1km):\n")
            f.write(f"  count={stats_B_minus_A['count']}, mean_A={stats_B_minus_A['mean_a']:.4f}, mean_B={stats_B_minus_A['mean_b']:.4f}, rmse={stats_B_minus_A['rmse']:.4f}, corr={stats_B_minus_A['corr']:.4f}\n")
            f.write("C (NALCMS 1km) vs A (Global 0.5° regridded to 1km):\n")
            f.write(f"  count={stats_C_minus_A['count']}, mean_A={stats_C_minus_A['mean_a']:.4f}, mean_C={stats_C_minus_A['mean_b']:.4f}, rmse={stats_C_minus_A['rmse']:.4f}, corr={stats_C_minus_A['corr']:.4f}\n")
            f.write("C (NALCMS 1km) vs B (Daymet 1km):\n")
            f.write(f"  count={stats_C_minus_B['count']}, mean_B={stats_C_minus_B['mean_a']:.4f}, mean_C={stats_C_minus_B['mean_b']:.4f}, rmse={stats_C_minus_B['rmse']:.4f}, corr={stats_C_minus_B['corr']:.4f}\n")
        # Choose plotting grids (allow overrides)
        xB_used = xB_plot_grid if xB_plot_grid is not None else xB_grid
        yB_used = yB_plot_grid if yB_plot_grid is not None else yB_grid
        xC_used = xC_plot_grid if xC_plot_grid is not None else xC_grid
        yC_used = yC_plot_grid if yC_plot_grid is not None else yC_grid
        kindB_used = kindB_override if kindB_override is not None else kindB
        kindC_used = kindC_override if kindC_override is not None else kindC
        # Downsample for plotting
        xB_ds, yB_ds, AonB_plot = downsample_for_plot(xB_used, yB_used, A_on_B)
        _, _, B_plot = downsample_for_plot(xB_used, yB_used, daB.values)
        xC_ds, yC_ds, C_plot = downsample_for_plot(xC_used, yC_used, daC.values)
        # Build domain masks from lon/lat finiteness to avoid plotting outside domain (even if values are zeros)
        lonB_ds, latB_ds, _ = downsample_for_plot(lonB, latB, A_on_B)
        lonC_ds, latC_ds, _ = downsample_for_plot(lonC, latC, daC.values)
        maskB_domain = np.isfinite(lonB_ds) & np.isfinite(latB_ds)
        maskC_domain = np.isfinite(lonC_ds) & np.isfinite(latC_ds)
        # Color limits
        if vmin_override is not None and vmax_override is not None:
            vmin = vmin_override
            vmax = vmax_override
        elif args.scale == "robust":
            vmin = float(np.nanpercentile(np.concatenate([AonB_plot.ravel(), B_plot.ravel(), C_plot.ravel()]), 2))
            vmax = float(np.nanpercentile(np.concatenate([AonB_plot.ravel(), B_plot.ravel(), C_plot.ravel()]), 98))
        else:
            vmin = args.map_min
            vmax = args.map_max
        # Orientation
        AonB_plot_oriented, extent_B, origin_B = prepare_imshow(AonB_plot, xB_ds, yB_ds)
        B_plot_oriented, _, _ = prepare_imshow(B_plot, xB_ds, yB_ds)
        C_plot_oriented, extent_C, origin_C = prepare_imshow(C_plot, xC_ds, yC_ds)
        # Orient domain masks to plotting orientation
        maskB_oriented, _, _ = prepare_imshow(maskB_domain.astype(float), xB_ds, yB_ds)
        maskB_oriented = maskB_oriented > 0.5
        maskC_oriented, _, _ = prepare_imshow(maskC_domain.astype(float), xC_ds, yC_ds)
        maskC_oriented = maskC_oriented > 0.5
        # Maps
        maps_file = comparison_dir / f"{var_name.lower()}{suffix}_maps.png"
        fig, axes = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
        cmap_map = make_cmap("viridis")
        # Apply domain masks so only valid grid is plotted (hide zeros outside domain)
        AonB_masked = np.where(maskB_oriented, AonB_plot_oriented, np.nan)
        B_masked = np.where(maskB_oriented, B_plot_oriented, np.nan)
        C_masked = np.where(maskC_oriented, C_plot_oriented, np.nan)
        im = axes[0].imshow(np.ma.masked_invalid(AonB_masked), origin=origin_B, extent=extent_B, cmap=cmap_map, vmin=vmin, vmax=vmax, interpolation="nearest")
        axes[0].set_title("Global 0.5° regridded to 1 km (nearest)")
        axes[0].set_xlabel("x" if kindB_used == "xy" else "Longitude (deg)")
        axes[0].set_ylabel("y" if kindB_used == "xy" else "Latitude (deg)")
        axes[1].imshow(np.ma.masked_invalid(B_masked), origin=origin_B, extent=extent_B, cmap=cmap_map, vmin=vmin, vmax=vmax, interpolation="nearest")
        axes[1].set_title("Daymet 1 km")
        axes[1].set_xlabel("x" if kindB_used == "xy" else "Longitude (deg)")
        axes[1].set_ylabel("y" if kindB_used == "xy" else "Latitude (deg)")
        axes[2].imshow(np.ma.masked_invalid(C_masked), origin=origin_C, extent=extent_C, cmap=cmap_map, vmin=vmin, vmax=vmax, interpolation="nearest")
        axes[2].set_title("NALCMS-derived 1 km")
        axes[2].set_xlabel("x" if kindC_used == "xy" else "Longitude (deg)")
        axes[2].set_ylabel("y" if kindC_used == "xy" else "Latitude (deg)")
        # Ensure background behind transparent NaNs is white
        for ax in axes:
            ax.set_facecolor("white")
        cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.9)
        cbar.set_label(var_name if per_layer_label is None else f"{var_name} {per_layer_label}")
        fig.savefig(maps_file, dpi=200)
        plt.close(fig)
        # Differences
        diff_BA = daB.values - A_on_B
        diff_CA = daC.values - A_on_B
        diff_CB = daC.values - daB.values
        _, _, diff_BA_plot = downsample_for_plot(xB_grid, yB_grid, diff_BA)
        _, _, diff_CA_plot = downsample_for_plot(xB_grid, yB_grid, diff_CA)
        _, _, diff_CB_plot = downsample_for_plot(xB_grid, yB_grid, diff_CB)
        if diff_lim_override is not None:
            dlim = diff_lim_override
        elif args.scale == "robust":
            dlim = float(np.nanpercentile(np.abs(np.concatenate([diff_BA_plot.ravel(), diff_CA_plot.ravel(), diff_CB_plot.ravel()])), 98))
        else:
            dlim = float(args.diff_lim)
        diff_BA_oriented, _, _ = prepare_imshow(diff_BA_plot, xB_ds, yB_ds)
        diff_CA_oriented, _, _ = prepare_imshow(diff_CA_plot, xB_ds, yB_ds)
        diff_CB_oriented, _, _ = prepare_imshow(diff_CB_plot, xB_ds, yB_ds)
        # Apply domain mask on B grid for all three differences (they are oriented on B grid)
        diff_BA_masked = np.where(maskB_oriented, diff_BA_oriented, np.nan)
        diff_CA_masked = np.where(maskB_oriented, diff_CA_oriented, np.nan)
        diff_CB_masked = np.where(maskB_oriented, diff_CB_oriented, np.nan)
        diffs_file = comparison_dir / f"{var_name.lower()}{suffix}_diffs.png"
        fig2, axes2 = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
        cmap_diff = make_cmap("coolwarm")
        im2 = axes2[0].imshow(np.ma.masked_invalid(diff_BA_masked), origin=origin_B, extent=extent_B, cmap=cmap_diff, vmin=-dlim, vmax=dlim, interpolation="nearest")
        axes2[0].set_title("Daymet 1 km minus Global (on 1 km)")
        axes2[0].set_xlabel("x" if kindB_used == "xy" else "Longitude (deg)")
        axes2[0].set_ylabel("y" if kindB_used == "xy" else "Latitude (deg)")
        axes2[1].imshow(np.ma.masked_invalid(diff_CA_masked), origin=origin_B, extent=extent_B, cmap=cmap_diff, vmin=-dlim, vmax=dlim, interpolation="nearest")
        axes2[1].set_title("NALCMS 1 km minus Global (on 1 km)")
        axes2[1].set_xlabel("x" if kindB_used == "xy" else "Longitude (deg)")
        axes2[1].set_ylabel("y" if kindB_used == "xy" else "Latitude (deg)")
        axes2[2].imshow(np.ma.masked_invalid(diff_CB_masked), origin=origin_B, extent=extent_B, cmap=cmap_diff, vmin=-dlim, vmax=dlim, interpolation="nearest")
        axes2[2].set_title("NALCMS 1 km minus Daymet 1 km")
        axes2[2].set_xlabel("x" if kindB_used == "xy" else "Longitude (deg)")
        axes2[2].set_ylabel("y" if kindB_used == "xy" else "Latitude (deg)")
        cbar2 = fig2.colorbar(im2, ax=axes2.ravel().tolist(), shrink=0.9)
        cbar2.set_label(f"{var_name} difference" if per_layer_label is None else f"{var_name} {per_layer_label} difference")
        fig2.savefig(diffs_file, dpi=200)
        plt.close(fig2)
        return maps_file, diffs_file, stat_file

    # Ensure PCT_URBAN still generates its special per-layer figure
    if "PCT_URBAN" in args.vars:
        out_maps = comparison_dir / "pct_urban_maps.png"
        out_diffs = comparison_dir / "pct_urban_diffs.png"
        out_stats = comparison_dir / "pct_urban_stats.txt"
        # Extract and total
        daA_raw = dsA["PCT_URBAN"].astype(np.float64)
        daB_raw = dsB["PCT_URBAN"].astype(np.float64)
        daC_raw = dsC["PCT_URBAN"].astype(np.float64)
        daA = get_total_urban(daA_raw)
        daB = get_total_urban(daB_raw)
        daC = get_total_urban(daC_raw)
        # Force x/y grids for all urban plots
        xB_xy, yB_xy, _kB = get_plot_grid_from_ds(dsB, "xy")
        xC_xy, yC_xy, _kC = get_plot_grid_from_ds(dsC, "xy")
        # Run generic plot for totals with fixed percentage limits [0, 100] and optional diff cap
        compute_stats_and_plots("PCT_URBAN", daA, daB, daC,
                                vmin_override=0.0, vmax_override=100.0,
                                diff_lim_override=100.0,
                                xB_plot_grid=xB_xy, yB_plot_grid=yB_xy,
                                xC_plot_grid=xC_xy, yC_plot_grid=yC_xy,
                                kindB_override="xy", kindC_override="xy")
        # Per-layer figure (keep previous behavior)
        layersA = get_urban_layers(daA_raw)
        layersB = get_urban_layers(daB_raw)
        layersC = get_urban_layers(daC_raw)
        A_layers_on_B = [nearest_regrid_to_target(latA, lonA, la.values, latB, lonB) for la in layersA[:3]]
        A_layers_plot = []
        B_layers_plot = []
        C_layers_plot = []
        for i in range(3):
            _, _, aplot = downsample_for_plot(xB_xy, yB_xy, A_layers_on_B[i])
            _, _, bplot = downsample_for_plot(xB_xy, yB_xy, layersB[i].values)
            _, _, cplot = downsample_for_plot(xC_xy, yC_xy, layersC[i].values)
            A_layers_plot.append(aplot)
            B_layers_plot.append(bplot)
            C_layers_plot.append(cplot)
        # Fixed percentage limits for per-layer plots
        vminL = 0.0
        vmaxL = 100.0
        out_layers = comparison_dir / "pct_urban_layers.png"
        fig3, axes3 = plt.subplots(3, 3, figsize=(18, 16), constrained_layout=True)
        A_layers_oriented = []
        B_layers_oriented = []
        C_layers_oriented = []
        # Use downsampled plotting grids; prepare orientation/extent
        xB_ds, yB_ds, _tmp = downsample_for_plot(xB_xy, yB_xy, A_layers_on_B[0])
        xC_ds, yC_ds, _tmp2 = downsample_for_plot(xC_xy, yC_xy, layersC[0].values)
        # Domain masks for layers (use lon/lat finiteness)
        lonB_ds, latB_ds, _m = downsample_for_plot(lonB, latB, A_layers_on_B[0])
        lonC_ds, latC_ds, _m2 = downsample_for_plot(lonC, latC, layersC[0].values)
        maskB_layers = np.isfinite(lonB_ds) & np.isfinite(latB_ds)
        maskC_layers = np.isfinite(lonC_ds) & np.isfinite(latC_ds)
        for j in range(3):
            a_or, extent_B_layers, origin_B_layers = prepare_imshow(A_layers_plot[j], xB_ds, yB_ds)
            b_or, _, _ = prepare_imshow(B_layers_plot[j], xB_ds, yB_ds)
            c_or, extent_C_layers, origin_C_layers = prepare_imshow(C_layers_plot[j], xC_ds, yC_ds)
            A_layers_oriented.append((a_or, extent_B_layers, origin_B_layers))
            B_layers_oriented.append((b_or, extent_B_layers, origin_B_layers))
            C_layers_oriented.append((c_or, extent_C_layers, origin_C_layers))
        # Oriented masks for layers
        maskB_layers_or, _, _ = prepare_imshow(maskB_layers.astype(float), xB_ds, yB_ds)
        maskB_layers_or = maskB_layers_or > 0.5
        maskC_layers_or, _, _ = prepare_imshow(maskC_layers.astype(float), xC_ds, yC_ds)
        maskC_layers_or = maskC_layers_or > 0.5
        last_im = None
        for j in range(3):
            a_im, a_ext, a_org = A_layers_oriented[j]
            a_im_masked = np.where(maskB_layers_or, a_im, np.nan)
            last_im = axes3[0, j].imshow(np.ma.masked_invalid(a_im_masked), origin=a_org, extent=a_ext, cmap="viridis", vmin=vminL, vmax=vmaxL, interpolation="nearest")
            axes3[0, j].set_title(f"Global (on 1 km) layer {j}")
            axes3[0, j].set_xlabel("x")
            axes3[0, j].set_ylabel("y")
            b_im, b_ext, b_org = B_layers_oriented[j]
            b_im_masked = np.where(maskB_layers_or, b_im, np.nan)
            axes3[1, j].imshow(np.ma.masked_invalid(b_im_masked), origin=b_org, extent=b_ext, cmap="viridis", vmin=vminL, vmax=vmaxL, interpolation="nearest")
            axes3[1, j].set_title(f"Daymet 1 km layer {j}")
            axes3[1, j].set_xlabel("x")
            axes3[1, j].set_ylabel("y")
            c_im, c_ext, c_org = C_layers_oriented[j]
            c_im_masked = np.where(maskC_layers_or, c_im, np.nan)
            axes3[2, j].imshow(np.ma.masked_invalid(c_im_masked), origin=c_org, extent=c_ext, cmap="viridis", vmin=vminL, vmax=vmaxL, interpolation="nearest")
            axes3[2, j].set_title(f"NALCMS 1 km layer {j}")
            axes3[2, j].set_xlabel("x")
            axes3[2, j].set_ylabel("y")
        cbar3 = fig3.colorbar(last_im, ax=axes3.ravel().tolist(), shrink=0.9)
        cbar3.set_label("PCT_URBAN per-layer")
        fig3.savefig(out_layers, dpi=200)
        plt.close(fig3)

    # Handle other requested variables
    for var in args.vars:
        v = var
        if v == "PCT_URBAN":
            continue  # already handled above
        if v not in dsA.variables and v not in dsB.variables and v not in dsC.variables:
            print(f"Skipping {var}: not found.")
            continue
        # Extract and cast
        if v in dsA.variables:
            daA_var = dsA[v].astype(np.float64)
        else:
            print(f"Variable {v} not in global dataset; skipping.")
            continue
        if v not in dsB.variables or v not in dsC.variables:
            print(f"Variable {v} missing from one of the 1 km datasets; skipping.")
            continue
        daB_var = dsB[v].astype(np.float64)
        daC_var = dsC[v].astype(np.float64)

        is_pct = isinstance(v, str) and v.startswith("PCT_")
        # Prepare forced xy grids for PCT_* percentage variables
        xB_xy, yB_xy, _kB_pct = (None, None, None)
        xC_xy, yC_xy, _kC_pct = (None, None, None)
        if is_pct:
            xB_xy, yB_xy, _kB_pct = get_plot_grid_from_ds(dsB, "xy")
            xC_xy, yC_xy, _kC_pct = get_plot_grid_from_ds(dsC, "xy")

        # natpft per-layer plotting
        if v == "PCT_NAT_PFT" and "natpft" in daA_var.dims:
            natpft_len = int(daA_var.sizes["natpft"])
            start = 0 if args.pft_start is None else max(0, args.pft_start)
            end = natpft_len - 1 if args.pft_end is None else min(natpft_len - 1, args.pft_end)
            for i in range(start, end + 1):
                daA_i = daA_var.isel(natpft=i)
                daB_i = daB_var.isel(natpft=i) if "natpft" in daB_var.dims else daB_var
                daC_i = daC_var.isel(natpft=i) if "natpft" in daC_var.dims else daC_var
                if is_pct:
                    compute_stats_and_plots(v, daA_i, daB_i, daC_i,
                                            suffix=f"_pft{i}", per_layer_label=f"natpft={i}",
                                            vmin_override=0.0, vmax_override=100.0,
                                            diff_lim_override=100.0,
                                            xB_plot_grid=xB_xy, yB_plot_grid=yB_xy,
                                            xC_plot_grid=xC_xy, yC_plot_grid=yC_xy,
                                            kindB_override="xy", kindC_override="xy")
                else:
                    compute_stats_and_plots(v, daA_i, daB_i, daC_i, suffix=f"_pft{i}", per_layer_label=f"natpft={i}")
        else:
            # 3D non-PFT variables: if leading dim exists (e.g., time), try to sum or select first; for now, prefer sum over 'numurbl' only
            if "numurbl" in daA_var.dims:
                daA_2d = daA_var.sum("numurbl")
                daB_2d = daB_var.sum("numurbl") if "numurbl" in daB_var.dims else daB_var
                daC_2d = daC_var.sum("numurbl") if "numurbl" in daC_var.dims else daC_var
            elif v not in daA_var.dims and len(daA_var.shape) > 2:
                # Fallback: take the first index along the leading dimension
                daA_2d = daA_var.isel({list(daA_var.dims)[0]: 0})
                daB_2d = daB_var.isel({list(daB_var.dims)[0]: 0}) if len(daB_var.shape) > 2 else daB_var
                daC_2d = daC_var.isel({list(daC_var.dims)[0]: 0}) if len(daC_var.shape) > 2 else daC_var
            else:
                daA_2d, daB_2d, daC_2d = daA_var, daB_var, daC_var
            if is_pct:
                compute_stats_and_plots(v, daA_2d, daB_2d, daC_2d,
                                        vmin_override=0.0, vmax_override=100.0,
                                        diff_lim_override=100.0,
                                        xB_plot_grid=xB_xy, yB_plot_grid=yB_xy,
                                        xC_plot_grid=xC_xy, yC_plot_grid=yC_xy,
                                        kindB_override="xy", kindC_override="xy")
            else:
                compute_stats_and_plots(v, daA_2d, daB_2d, daC_2d)

    print("Completed all requested comparisons.")


if __name__ == "__main__":
    main()


