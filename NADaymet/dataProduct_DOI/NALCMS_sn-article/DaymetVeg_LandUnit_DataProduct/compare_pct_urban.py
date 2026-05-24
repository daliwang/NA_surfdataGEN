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


def main():
    parser = argparse.ArgumentParser(description="Compare PCT_URBAN across two global surfdata datasets (current/past) and NALCMS Daymet grid.")
    parser.add_argument("--scale", choices=["robust", "fixed"], default="robust",
                        help="Color scaling mode: 'robust' uses 2nd/98th percentiles; 'fixed' uses provided limits.")
    parser.add_argument("--map-min", type=float, default=0.0,
                        help="Fixed vmin for maps when --scale=fixed.")
    parser.add_argument("--map-max", type=float, default=100.0,
                        help="Fixed vmax for maps when --scale=fixed.")
    parser.add_argument("--diff-lim", type=float, default=100.0,
                        help="Fixed absolute limit for difference plots when --scale=fixed (range [-diff-lim, +diff-lim]).")
    parser.add_argument("--global-current-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/landuse.PCT_subset_last.nc"),
                        help="Path to current landuse global surfdata file (contains PCT_URBAN).")
    parser.add_argument("--global-past-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/surfdata_0.5x0.5_simyr1850_c200609_with_TOP.subset.nc"),
                        help="Path to past (e.g., 1850) global surfdata file (contains PCT_URBAN).")
    parser.add_argument("--nalcms-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260122.nc"),
                        help="Path to NALCMS Daymet grid surfdata file (contains PCT_URBAN).")
    parser.add_argument("--outdir", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/Surfdata_c260122_comparison_plots"),
                        help="Directory to write output figures and stats.")
    args = parser.parse_args()

    out_dir = args.outdir
    out_dir.mkdir(parents=True, exist_ok=True)
    dataset_global1 = args.global_current_file
    dataset_global2 = args.global_past_file
    dataset_nalcms = args.nalcms_file

    out_maps = out_dir / "pct_urban_maps.png"
    out_diffs = out_dir / "pct_urban_diffs.png"
    out_stats = out_dir / "pct_urban_stats.txt"

    dsA = load_dataset(dataset_global1)       # Global current (e.g., 2016)
    dsB = load_dataset(dataset_global2)       # Global past (e.g., 1850)
    dsC = load_dataset(dataset_nalcms)        # NALCMS Daymet grid (e.g., 2020)

    # Extract PCT_URBAN and total if needed
    daA_raw = dsA["PCT_URBAN"].astype(np.float64)
    daB_raw = dsB["PCT_URBAN"].astype(np.float64)
    daC_raw = dsC["PCT_URBAN"].astype(np.float64)
    daA = get_total_urban(daA_raw)
    daB = get_total_urban(daB_raw)
    daC = get_total_urban(daC_raw)

    # Get lat/lon for each dataset
    latA, lonA = get_lat_lon_from_ds(dsA)
    latB, lonB = get_lat_lon_from_ds(dsB)
    latC, lonC = get_lat_lon_from_ds(dsC)

    # Regrid both globals to the Daymet/NALCMS grid via nearest-neighbor in lat/lon
    A_on_C = nearest_regrid_to_target(latA, lonA, daA.values, latC, lonC)
    B_on_C = nearest_regrid_to_target(latB, lonB, daB.values, latC, lonC)

    # Build masks for stats
    valid_AonC = np.isfinite(A_on_C)
    valid_BonC = np.isfinite(B_on_C)
    valid_C = np.isfinite(daC.values)
    common_A_B = valid_AonC & valid_BonC
    common_A_C = valid_AonC & valid_C
    common_B_C = valid_BonC & valid_C

    # Compute stats
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

    stats_B_minus_A = stats(A_on_C, B_on_C, common_A_B)
    stats_C_minus_A = stats(A_on_C, daC.values, common_A_C)
    stats_C_minus_B = stats(B_on_C, daC.values, common_B_C)

    # Save stats
    with open(out_stats, "w") as f:
        f.write("PCT_URBAN comparison stats (units as in inputs):\n")
        f.write("B (Global_1850 on Daymet grid) vs A (Global_2016 on Daymet grid):\n")
        f.write(f"  count={stats_B_minus_A['count']}, mean_A={stats_B_minus_A['mean_a']:.4f}, mean_B={stats_B_minus_A['mean_b']:.4f}, rmse={stats_B_minus_A['rmse']:.4f}, corr={stats_B_minus_A['corr']:.4f}\n")
        f.write("C (NALCMS Daymet) vs A (Global_2016 on Daymet):\n")
        f.write(f"  count={stats_C_minus_A['count']}, mean_A={stats_C_minus_A['mean_a']:.4f}, mean_C={stats_C_minus_A['mean_b']:.4f}, rmse={stats_C_minus_A['rmse']:.4f}, corr={stats_C_minus_A['corr']:.4f}\n")
        f.write("C (NALCMS Daymet) vs B (Global_1850 on Daymet):\n")
        f.write(f"  count={stats_C_minus_B['count']}, mean_B={stats_C_minus_B['mean_a']:.4f}, mean_C={stats_C_minus_B['mean_b']:.4f}, rmse={stats_C_minus_B['rmse']:.4f}, corr={stats_C_minus_B['corr']:.4f}\n")

    # Prepare data for plotting (downsample for speed)
    xC, yC, A_plot = downsample_for_plot(lonC, latC, A_on_C)
    _, _, B_plot = downsample_for_plot(lonC, latC, B_on_C)
    _, _, C_plot = downsample_for_plot(lonC, latC, daC.values)

    # Determine color limits from combined data
    if args.scale == "robust":
        vmin = float(np.nanpercentile(np.concatenate([A_plot.ravel(), B_plot.ravel(), C_plot.ravel()]), 2))
        vmax = float(np.nanpercentile(np.concatenate([A_plot.ravel(), B_plot.ravel(), C_plot.ravel()]), 98))
    else:
        vmin = args.map_min
        vmax = args.map_max

    # Prepare imshow orientation/extent per grid
    A_oriented, extent_C, origin_C = prepare_imshow(A_plot, xC, yC)
    B_oriented, _, _ = prepare_imshow(B_plot, xC, yC)
    C_oriented, _, _ = prepare_imshow(C_plot, xC, yC)

    # Figure 1: three maps (use imshow with geographic extent to avoid NaNs in coord grids)
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
    im = axes[0].imshow(A_oriented, origin=origin_C, extent=extent_C, cmap="viridis", vmin=vmin, vmax=vmax, interpolation="nearest")
    axes[0].set_title("Global_2016 (on Daymet grid)")
    axes[0].set_xlabel("Longitude (deg)")
    axes[0].set_ylabel("Latitude (deg)")

    axes[1].imshow(B_oriented, origin=origin_C, extent=extent_C, cmap="viridis", vmin=vmin, vmax=vmax, interpolation="nearest")
    axes[1].set_title("Global_1850 (on Daymet grid)")
    axes[1].set_xlabel("Longitude (deg)")
    axes[1].set_ylabel("Latitude (deg)")

    axes[2].imshow(C_oriented, origin=origin_C, extent=extent_C, cmap="viridis", vmin=vmin, vmax=vmax, interpolation="nearest")
    axes[2].set_title("NALCMS_2020")
    axes[2].set_xlabel("Longitude (deg)")
    axes[2].set_ylabel("Latitude (deg)")
    cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.9)
    cbar.set_label("PCT_URBAN")
    fig.savefig(out_maps, dpi=200)
    plt.close(fig)

    # Figure 2: differences (B-A, C-A, C-B) on B grid where possible
    diff_BA = B_on_C - A_on_C
    diff_CA = daC.values - A_on_C
    diff_CB = daC.values - B_on_C
    _, _, diff_BA_plot = downsample_for_plot(lonC, latC, diff_BA)
    _, _, diff_CA_plot = downsample_for_plot(lonC, latC, diff_CA)
    _, _, diff_CB_plot = downsample_for_plot(lonC, latC, diff_CB)

    if args.scale == "robust":
        dlim = float(np.nanpercentile(np.abs(np.concatenate([diff_BA_plot.ravel(), diff_CA_plot.ravel(), diff_CB_plot.ravel()])), 98))
    else:
        dlim = float(args.diff_lim)
    fig2, axes2 = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
    # Orient diff plots on C grid
    diff_BA_oriented, _, _ = prepare_imshow(diff_BA_plot, xC, yC)
    diff_CA_oriented, _, _ = prepare_imshow(diff_CA_plot, xC, yC)
    diff_CB_oriented, _, _ = prepare_imshow(diff_CB_plot, xC, yC)

    im2 = axes2[0].imshow(diff_BA_oriented, origin=origin_C, extent=extent_C, cmap="coolwarm", vmin=-dlim, vmax=dlim, interpolation="nearest")
    axes2[0].set_title("Global_1850 - Global_2016")
    axes2[0].set_xlabel("Longitude (deg)")
    axes2[0].set_ylabel("Latitude (deg)")

    axes2[1].imshow(diff_CA_oriented, origin=origin_C, extent=extent_C, cmap="coolwarm", vmin=-dlim, vmax=dlim, interpolation="nearest")
    axes2[1].set_title("NALCMS_2020 - Global_2016")
    axes2[1].set_xlabel("Longitude (deg)")
    axes2[1].set_ylabel("Latitude (deg)")

    axes2[2].imshow(diff_CB_oriented, origin=origin_C, extent=extent_C, cmap="coolwarm", vmin=-dlim, vmax=dlim, interpolation="nearest")
    axes2[2].set_title("NALCMS_2020 - Global_1850")
    axes2[2].set_xlabel("Longitude (deg)")
    axes2[2].set_ylabel("Latitude (deg)")
    cbar2 = fig2.colorbar(im2, ax=axes2.ravel().tolist(), shrink=0.9)
    cbar2.set_label("PCT_URBAN difference")
    fig2.savefig(out_diffs, dpi=200)
    plt.close(fig2)

    # Figure 3: per-layer visualization (A regridded layers, B layers, C layers)
    layersA = get_urban_layers(daA_raw)
    layersB = get_urban_layers(daB_raw)
    layersC = get_urban_layers(daC_raw)

    # Regrid A layers to B grid
    A_layers_on_B = []
    for la in layersA[:3]:
        A_layers_on_B.append(
            nearest_regrid_to_target(latA, lonA, la.values, latB, lonB)
        )

    # Downsample for plotting
    A_layers_plot = []
    B_layers_plot = []
    C_layers_plot = []
    xB_layers = None
    yB_layers = None
    xC_layers = None
    yC_layers = None
    for i in range(3):
        # Capture downsampled lon/lat once for each grid
        xb, yb, aplot = downsample_for_plot(lonB, latB, A_layers_on_B[i])
        if xB_layers is None:
            xB_layers, yB_layers = xb, yb
        _, _, bplot = downsample_for_plot(lonB, latB, layersB[i].values)
        xc, yc, cplot = downsample_for_plot(lonC, latC, layersC[i].values)
        if xC_layers is None:
            xC_layers, yC_layers = xc, yc
        A_layers_plot.append(aplot)
        B_layers_plot.append(bplot)
        C_layers_plot.append(cplot)

    # Common color limits across all layers and datasets
    if args.scale == "robust":
        all_layer_vals = np.concatenate([x.ravel() for x in (A_layers_plot + B_layers_plot + C_layers_plot)])
        vminL = float(np.nanpercentile(all_layer_vals, 2))
        vmaxL = float(np.nanpercentile(all_layer_vals, 98))
    else:
        vminL = args.map_min
        vmaxL = args.map_max

    out_layers = out_dir / "pct_urban_layers.png"
    fig3, axes3 = plt.subplots(3, 3, figsize=(18, 16), constrained_layout=True)
    # Row titles: A_on_B, B, C
    row_titles = ["Global (on 1 km) layer", "Daymet 1 km layer", "NALCMS 1 km layer"]
    col_titles = ["numurbl=0", "numurbl=1", "numurbl=2"]

    # Prepare orientation/extent per grid for layers
    # Use B grid orientation for A_on_B and B layers, C grid for C layers
    # Recompute oriented arrays for imshow
    A_layers_oriented = []
    B_layers_oriented = []
    C_layers_oriented = []
    # Make orientation/extent using the downsampled lon/lat captured for each grid
    for j in range(3):
        a_or, extent_B_layers, origin_B_layers = prepare_imshow(A_layers_plot[j], xB_layers, yB_layers)
        b_or, _, _ = prepare_imshow(B_layers_plot[j], xB_layers, yB_layers)
        c_or, extent_C_layers, origin_C_layers = prepare_imshow(C_layers_plot[j], xC_layers, yC_layers)
        A_layers_oriented.append((a_or, extent_B_layers, origin_B_layers))
        B_layers_oriented.append((b_or, extent_B_layers, origin_B_layers))
        C_layers_oriented.append((c_or, extent_C_layers, origin_C_layers))

    last_im = None
    for j in range(3):
        # A on B grid
        a_im, a_ext, a_org = A_layers_oriented[j]
        last_im = axes3[0, j].imshow(a_im, origin=a_org, extent=a_ext, cmap="viridis", vmin=vminL, vmax=vmaxL, interpolation="nearest")
        axes3[0, j].set_title(f"{row_titles[0]} {j}")
        axes3[0, j].set_xlabel("Longitude (deg)")
        axes3[0, j].set_ylabel("Latitude (deg)")

        # B grid
        b_im, b_ext, b_org = B_layers_oriented[j]
        axes3[1, j].imshow(b_im, origin=b_org, extent=b_ext, cmap="viridis", vmin=vminL, vmax=vmaxL, interpolation="nearest")
        axes3[1, j].set_title(f"{row_titles[1]} {j}")
        axes3[1, j].set_xlabel("Longitude (deg)")
        axes3[1, j].set_ylabel("Latitude (deg)")

        # C grid
        c_im, c_ext, c_org = C_layers_oriented[j]
        axes3[2, j].imshow(c_im, origin=c_org, extent=c_ext, cmap="viridis", vmin=vminL, vmax=vmaxL, interpolation="nearest")
        axes3[2, j].set_title(f"{row_titles[2]} {j}")
        axes3[2, j].set_xlabel("Longitude (deg)")
        axes3[2, j].set_ylabel("Latitude (deg)")

    cbar3 = fig3.colorbar(last_im, ax=axes3.ravel().tolist(), shrink=0.9)
    cbar3.set_label("PCT_URBAN per-layer")
    fig3.savefig(out_layers, dpi=200)
    plt.close(fig3)

    print(f"Wrote figures:\n  {out_maps}\n  {out_diffs}\nWrote stats:\n  {out_stats}")


if __name__ == "__main__":
    main()


