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
    lon_candidates = ["LONGXY", "lon", "longitude", "LON"]
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


def prepare_imshow(z, lon_grid, lat_grid):
    """
    Prepare array and parameters for imshow:
    - Flip left/right if longitude decreases from left to right
    - Choose origin='upper' if latitude decreases from top row to bottom row
    - Compute extent from lon/lat
    """
    lon = lon_grid
    lat = lat_grid
    z_plot = z
    # Horizontal orientation (left to right)
    try:
        lon_left = np.nanmean(lon[:, 0])
        lon_right = np.nanmean(lon[:, -1])
        if np.isfinite(lon_left) and np.isfinite(lon_right) and lon_left > lon_right:
            z_plot = np.fliplr(z_plot)
            lon = np.fliplr(lon)
    except Exception:
        pass
    # Vertical orientation (top to bottom)
    origin = "lower"
    try:
        lat_top = np.nanmean(lat[0, :])
        lat_bottom = np.nanmean(lat[-1, :])
        if np.isfinite(lat_top) and np.isfinite(lat_bottom) and lat_top > lat_bottom:
            origin = "upper"
    except Exception:
        origin = "lower"
    # Extent
    extent = [float(np.nanmin(lon)), float(np.nanmax(lon)), float(np.nanmin(lat)), float(np.nanmax(lat))]
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

    # Helpers for generic variable processing
    def compute_stats_and_plots(var_name: str, daA: xr.DataArray, daB: xr.DataArray, daC: xr.DataArray,
                                suffix: str = "", per_layer_label: str | None = None):
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
        # Downsample for plotting
        xB, yB, AonB_plot = downsample_for_plot(lonB, latB, A_on_B)
        _, _, B_plot = downsample_for_plot(lonB, latB, daB.values)
        xC, yC, C_plot = downsample_for_plot(lonC, latC, daC.values)
        # Color limits
        if args.scale == "robust":
            vmin = float(np.nanpercentile(np.concatenate([AonB_plot.ravel(), B_plot.ravel(), C_plot.ravel()]), 2))
            vmax = float(np.nanpercentile(np.concatenate([AonB_plot.ravel(), B_plot.ravel(), C_plot.ravel()]), 98))
        else:
            vmin = args.map_min
            vmax = args.map_max
        # Orientation
        AonB_plot_oriented, extent_B, origin_B = prepare_imshow(AonB_plot, xB, yB)
        B_plot_oriented, _, _ = prepare_imshow(B_plot, xB, yB)
        C_plot_oriented, extent_C, origin_C = prepare_imshow(C_plot, xC, yC)
        # Build domain masks from lon/lat finiteness to avoid plotting outside domain (even if values are zeros)
        maskB = np.isfinite(xB) & np.isfinite(yB)
        maskB_oriented, _, _ = prepare_imshow(maskB.astype(float), xB, yB)
        maskB_oriented = maskB_oriented > 0.5
        maskC = np.isfinite(xC) & np.isfinite(yC)
        maskC_oriented, _, _ = prepare_imshow(maskC.astype(float), xC, yC)
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
        axes[0].set_xlabel("Longitude (deg)")
        axes[0].set_ylabel("Latitude (deg)")
        axes[1].imshow(np.ma.masked_invalid(B_masked), origin=origin_B, extent=extent_B, cmap=cmap_map, vmin=vmin, vmax=vmax, interpolation="nearest")
        axes[1].set_title("Daymet 1 km")
        axes[1].set_xlabel("Longitude (deg)")
        axes[1].set_ylabel("Latitude (deg)")
        axes[2].imshow(np.ma.masked_invalid(C_masked), origin=origin_C, extent=extent_C, cmap=cmap_map, vmin=vmin, vmax=vmax, interpolation="nearest")
        axes[2].set_title("NALCMS-derived 1 km")
        axes[2].set_xlabel("Longitude (deg)")
        axes[2].set_ylabel("Latitude (deg)")
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
        _, _, diff_BA_plot = downsample_for_plot(lonB, latB, diff_BA)
        _, _, diff_CA_plot = downsample_for_plot(lonB, latB, diff_CA)
        _, _, diff_CB_plot = downsample_for_plot(lonB, latB, diff_CB)
        if args.scale == "robust":
            dlim = float(np.nanpercentile(np.abs(np.concatenate([diff_BA_plot.ravel(), diff_CA_plot.ravel(), diff_CB_plot.ravel()])), 98))
        else:
            dlim = float(args.diff_lim)
        diff_BA_oriented, _, _ = prepare_imshow(diff_BA_plot, xB, yB)
        diff_CA_oriented, _, _ = prepare_imshow(diff_CA_plot, xB, yB)
        diff_CB_oriented, _, _ = prepare_imshow(diff_CB_plot, xB, yB)
        diffs_file = comparison_dir / f"{var_name.lower()}{suffix}_diffs.png"
        fig2, axes2 = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
        cmap_diff = make_cmap("coolwarm")
        im2 = axes2[0].imshow(np.ma.masked_invalid(diff_BA_oriented), origin=origin_B, extent=extent_B, cmap=cmap_diff, vmin=-dlim, vmax=dlim, interpolation="nearest")
        axes2[0].set_title("Daymet 1 km minus Global (on 1 km)")
        axes2[0].set_xlabel("Longitude (deg)")
        axes2[0].set_ylabel("Latitude (deg)")
        axes2[1].imshow(np.ma.masked_invalid(diff_CA_oriented), origin=origin_B, extent=extent_B, cmap=cmap_diff, vmin=-dlim, vmax=dlim, interpolation="nearest")
        axes2[1].set_title("NALCMS 1 km minus Global (on 1 km)")
        axes2[1].set_xlabel("Longitude (deg)")
        axes2[1].set_ylabel("Latitude (deg)")
        axes2[2].imshow(np.ma.masked_invalid(diff_CB_oriented), origin=origin_B, extent=extent_B, cmap=cmap_diff, vmin=-dlim, vmax=dlim, interpolation="nearest")
        axes2[2].set_title("NALCMS 1 km minus Daymet 1 km")
        axes2[2].set_xlabel("Longitude (deg)")
        axes2[2].set_ylabel("Latitude (deg)")
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
        # Run generic plot for totals
        compute_stats_and_plots("PCT_URBAN", daA, daB, daC)
        # Per-layer figure (keep previous behavior)
        layersA = get_urban_layers(daA_raw)
        layersB = get_urban_layers(daB_raw)
        layersC = get_urban_layers(daC_raw)
        A_layers_on_B = [nearest_regrid_to_target(latA, lonA, la.values, latB, lonB) for la in layersA[:3]]
        A_layers_plot = []
        B_layers_plot = []
        C_layers_plot = []
        for i in range(3):
            _, _, aplot = downsample_for_plot(lonB, latB, A_layers_on_B[i])
            _, _, bplot = downsample_for_plot(lonB, latB, layersB[i].values)
            _, _, cplot = downsample_for_plot(lonC, latC, layersC[i].values)
            A_layers_plot.append(aplot)
            B_layers_plot.append(bplot)
            C_layers_plot.append(cplot)
        if args.scale == "robust":
            all_layer_vals = np.concatenate([x.ravel() for x in (A_layers_plot + B_layers_plot + C_layers_plot)])
            vminL = float(np.nanpercentile(all_layer_vals, 2))
            vmaxL = float(np.nanpercentile(all_layer_vals, 98))
        else:
            vminL = args.map_min
            vmaxL = args.map_max
        out_layers = comparison_dir / "pct_urban_layers.png"
        fig3, axes3 = plt.subplots(3, 3, figsize=(18, 16), constrained_layout=True)
        A_layers_oriented = []
        B_layers_oriented = []
        C_layers_oriented = []
        # Use downsampled lon/lat grids; prepare orientation/extent
        xB, yB, _tmp = downsample_for_plot(lonB, latB, A_layers_on_B[0])
        xC, yC, _tmp2 = downsample_for_plot(lonC, latC, layersC[0].values)
        for j in range(3):
            a_or, extent_B_layers, origin_B_layers = prepare_imshow(A_layers_plot[j], xB, yB)
            b_or, _, _ = prepare_imshow(B_layers_plot[j], xB, yB)
            c_or, extent_C_layers, origin_C_layers = prepare_imshow(C_layers_plot[j], xC, yC)
            A_layers_oriented.append((a_or, extent_B_layers, origin_B_layers))
            B_layers_oriented.append((b_or, extent_B_layers, origin_B_layers))
            C_layers_oriented.append((c_or, extent_C_layers, origin_C_layers))
        last_im = None
        for j in range(3):
            a_im, a_ext, a_org = A_layers_oriented[j]
            last_im = axes3[0, j].imshow(a_im, origin=a_org, extent=a_ext, cmap="viridis", vmin=vminL, vmax=vmaxL, interpolation="nearest")
            axes3[0, j].set_title(f"Global (on 1 km) layer {j}")
            axes3[0, j].set_xlabel("Longitude (deg)")
            axes3[0, j].set_ylabel("Latitude (deg)")
            b_im, b_ext, b_org = B_layers_oriented[j]
            axes3[1, j].imshow(b_im, origin=b_org, extent=b_ext, cmap="viridis", vmin=vminL, vmax=vmaxL, interpolation="nearest")
            axes3[1, j].set_title(f"Daymet 1 km layer {j}")
            axes3[1, j].set_xlabel("Longitude (deg)")
            axes3[1, j].set_ylabel("Latitude (deg)")
            c_im, c_ext, c_org = C_layers_oriented[j]
            axes3[2, j].imshow(c_im, origin=c_org, extent=c_ext, cmap="viridis", vmin=vminL, vmax=vmaxL, interpolation="nearest")
            axes3[2, j].set_title(f"NALCMS 1 km layer {j}")
            axes3[2, j].set_xlabel("Longitude (deg)")
            axes3[2, j].set_ylabel("Latitude (deg)")
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

        # natpft per-layer plotting
        if v == "PCT_NAT_PFT" and "natpft" in daA_var.dims:
            natpft_len = int(daA_var.sizes["natpft"])
            start = 0 if args.pft_start is None else max(0, args.pft_start)
            end = natpft_len - 1 if args.pft_end is None else min(natpft_len - 1, args.pft_end)
            for i in range(start, end + 1):
                daA_i = daA_var.isel(natpft=i)
                daB_i = daB_var.isel(natpft=i) if "natpft" in daB_var.dims else daB_var
                daC_i = daC_var.isel(natpft=i) if "natpft" in daC_var.dims else daC_var
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
            compute_stats_and_plots(v, daA_2d, daB_2d, daC_2d)

    print("Completed all requested comparisons.")


if __name__ == "__main__":
    main()


