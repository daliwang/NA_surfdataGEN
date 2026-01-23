import argparse
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree


def normalize_longitude(lon: np.ndarray) -> np.ndarray:
    lon = np.asarray(lon, dtype=float)
    return np.mod(lon, 360.0)


def load_dataset(path: Path) -> xr.Dataset:
    return xr.open_dataset(path)


def get_lat_lon_from_ds(ds: xr.Dataset):
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


def nearest_regrid_to_target(lat_src, lon_src, data_src, lat_tgt, lon_tgt):
    # Ensure 2D lat/lon for source
    if lat_src.ndim == 1 and lon_src.ndim == 1:
        lat_src = np.tile(lat_src[:, np.newaxis], (1, lon_src.size))
        lon_src = np.tile(lon_src[np.newaxis, :], (lat_src.shape[0], 1))
    # Ensure 2D for target
    if lat_tgt.ndim == 1 and lon_tgt.ndim == 1:
        lat_tgt, lon_tgt = np.meshgrid(lat_tgt, lon_tgt, indexing="ij")
    # Flatten valid points
    mask_src = np.isfinite(lat_src) & np.isfinite(lon_src) & np.isfinite(data_src)
    lat_src_f = lat_src[mask_src]
    lon_src_f = lon_src[mask_src]
    data_src_f = data_src[mask_src]
    # Normalize longitudes to [0, 360)
    lon_src_f = normalize_longitude(lon_src_f)
    lon_tgt_norm = normalize_longitude(lon_tgt)
    # KDTree in (lat, lon)
    pts_src = np.column_stack((lat_src_f.ravel(), lon_src_f.ravel()))
    tree = cKDTree(pts_src)
    # Target
    tgt_shape = lat_tgt.shape
    lat_tgt_flat = lat_tgt.ravel()
    lon_tgt_flat = lon_tgt_norm.ravel()
    valid_tgt = np.isfinite(lat_tgt_flat) & np.isfinite(lon_tgt_flat)
    out = np.full(lat_tgt_flat.shape, np.nan, dtype=data_src_f.dtype)
    idxs = np.where(valid_tgt)[0]
    if idxs.size > 0:
        _, nn = tree.query(np.column_stack((lat_tgt_flat[idxs], lon_tgt_flat[idxs])), k=1)
        out[idxs] = data_src_f[nn]
    return out.reshape(tgt_shape)

def nearest_on_regular_lonlat(lat1d: np.ndarray, lon1d: np.ndarray, data2d: np.ndarray, lat_tgt: np.ndarray, lon_tgt: np.ndarray) -> np.ndarray:
    # Ensure 1D coords
    lat1d = np.asarray(lat1d).astype(float)
    lon1d = np.asarray(lon1d).astype(float)
    # Normalize lon_tgt to same wrap as lon1d (assume lon1d in [min,max], may be [0,360) or [-180,180])
    lon_tgt_norm = lon_tgt.copy().astype(float)
    if np.nanmin(lon1d) >= 0.0 and np.nanmax(lon1d) <= 360.0:
        lon_tgt_norm = np.mod(lon_tgt_norm, 360.0)
    else:
        lon_tgt_norm = ((lon_tgt_norm + 180.0) % 360.0) - 180.0
    # Handle ascending/descending
    def nearest_idx(vals, grid):
        asc = grid[0] <= grid[-1]
        g = grid if asc else grid[::-1]
        v = vals if asc else -vals
        if not asc:
            g = -g
        idx = np.searchsorted(g, v)
        idx = np.clip(idx, 1, g.size - 1)
        left = g[idx - 1]
        right = g[idx]
        choose_right = (np.abs(v - right) < np.abs(v - left))
        out = idx.copy()
        out[~choose_right] = idx[~choose_right] - 1
        if asc:
            return out
        else:
            # map back to original indexing
            return (g.size - 1) - out
    # Compute indices
    if lat_tgt.ndim == 1 and lon_tgt_norm.ndim == 1:
        lat_tgt, lon_tgt_norm = np.meshgrid(lat_tgt, lon_tgt_norm, indexing="ij")
    iy = nearest_idx(lat_tgt, lat1d)
    ix = nearest_idx(lon_tgt_norm, lon1d)
    return data2d[iy, ix]

def downsample_for_plot(x, y, z, max_points=1_000_000):
    ny, nx = z.shape
    if nx * ny > max_points:
        stride = max(1, int(np.ceil(np.sqrt((nx * ny) / max_points))))
    else:
        stride = 1
    return x[::stride, ::stride], y[::stride, ::stride], z[::stride, ::stride]


def prepare_imshow(z, x_grid, y_grid):
    xg = x_grid
    yg = y_grid
    z_plot = z
    # Flip left/right if needed
    try:
        left = np.nanmean(xg[:, 0])
        right = np.nanmean(xg[:, -1])
        if np.isfinite(left) and np.isfinite(right) and left > right:
            z_plot = np.fliplr(z_plot)
            xg = np.fliplr(xg)
    except Exception:
        pass
    origin = "lower"
    try:
        top = np.nanmean(yg[0, :])
        bottom = np.nanmean(yg[-1, :])
        if np.isfinite(top) and np.isfinite(bottom) and top > bottom:
            origin = "upper"
    except Exception:
        origin = "lower"
    extent = [float(np.nanmin(xg)), float(np.nanmax(xg)),
              float(np.nanmin(yg)), float(np.nanmax(yg))]
    return z_plot, extent, origin


def make_cmap(name: str):
    cmap = plt.get_cmap(name).copy()
    cmap.set_bad(color=(0.0, 0.0, 0.0, 0.0))
    return cmap

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
    # Fallback: try 1D lon/lat if present (used as x/y)
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
        xg, yg = np.meshgrid(x_val, y_val, indexing="xy")
        return xg, yg
    if x_val.ndim == 2 and y_val.ndim == 2:
        return x_val, y_val
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
            lat, lon = get_lat_lon_from_ds(ds)
            return lon, lat, "lonlat"
    lat, lon = get_lat_lon_from_ds(ds)
    return lon, lat, "lonlat"

def main():
    parser = argparse.ArgumentParser(description="Compare LULC 2020 1km PCT_LAKE to NALCMS surfdata Daymet 1km PCT_LAKE.")
    parser.add_argument("--lulc-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/references/LULC/PCT_LAKE_2020_1k_c230606.nc"))
    parser.add_argument("--nalcms-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c251230.subset.nc"))
    parser.add_argument("--var", type=str, default="PCT_LAKE")
    parser.add_argument("--outdir", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/lulc_2020_lake_compare"))
    parser.add_argument("--scale", choices=["robust", "fixed"], default="fixed")
    parser.add_argument("--map-min", type=float, default=0.0)
    parser.add_argument("--map-max", type=float, default=100.0)
    parser.add_argument("--diff-lim", type=float, default=100.0)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    dsL = load_dataset(args.lulc_file)
    dsN = load_dataset(args.nalcms_file)

    if args.var not in dsL.data_vars:
        raise SystemExit(f"{args.var} not found in LULC file.")
    if args.var not in dsN.data_vars:
        raise SystemExit(f"{args.var} not found in NALCMS file.")

    latL, lonL = get_lat_lon_from_ds(dsL)
    latN, lonN = get_lat_lon_from_ds(dsN)

    vL = dsL[args.var].astype(np.float64).values
    vN = dsN[args.var].astype(np.float64).values

    # Regrid LULC -> Daymet (NALCMS) grid using nearest in lat/lon
    # Prefer regular-grid nearest if LULC uses 1D lat/lon (fast and memory efficient)
    try:
        latL1d = dsL.coords["lat"].values
        lonL1d = dsL.coords["lon"].values
        L_on_N = nearest_on_regular_lonlat(latL1d, lonL1d, vL, latN, lonN)
    except Exception:
        # Fallback to KDTree if 1D coords are not available
        L_on_N = nearest_regrid_to_target(latL, lonL, vL, latN, lonN)

    # Downsample for plotting
    # Prefer Daymet/NALCMS 1 km x/y plotting grid similar to compare_pct_nat_pft.py
    xN_grid, yN_grid, kindN = get_plot_grid_from_ds(dsN, "xy")
    xN_ds, yN_ds, L_plot = downsample_for_plot(xN_grid, yN_grid, L_on_N)
    _, _, N_plot = downsample_for_plot(xN_grid, yN_grid, vN)

    # Domain mask based on Daymet/NALCMS lon/lat finiteness (hide outside domain)
    _, _, lonN_ds = downsample_for_plot(xN_grid, yN_grid, lonN)
    _, _, latN_ds = downsample_for_plot(xN_grid, yN_grid, latN)
    maskN = np.isfinite(lonN_ds) & np.isfinite(latN_ds)

    # Scaling
    if args.scale == "robust":
        vals = np.concatenate([L_plot.ravel(), N_plot.ravel()])
        vmin = float(np.nanpercentile(vals, 2))
        vmax = float(np.nanpercentile(vals, 98))
    else:
        vmin, vmax = args.map_min, args.map_max

    # Orientation and extent
    L_or, extent, origin = prepare_imshow(L_plot, xN_ds, yN_ds)
    N_or, _, _ = prepare_imshow(N_plot, xN_ds, yN_ds)
    mask_or, _, _ = prepare_imshow(maskN.astype(float), xN_ds, yN_ds)
    mask_or = mask_or > 0.5

    # Maps
    maps_file = args.outdir / "pct_lake_lulc2020_vs_nalcms_maps.png"
    fig, axes = plt.subplots(1, 2, figsize=(12, 6), constrained_layout=True)
    for ax in axes:
        ax.set_facecolor("white")
    cmap = make_cmap("viridis")
    L_masked = np.where(mask_or, L_or, np.nan)
    N_masked = np.where(mask_or, N_or, np.nan)
    im0 = axes[0].imshow(np.ma.masked_invalid(L_masked), origin=origin, extent=extent, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    axes[0].set_title("LULC 2020 PCT_LAKE (on Daymet grid)")
    axes[0].set_xlabel("x" if kindN == "xy" else "Longitude (deg)")
    axes[0].set_ylabel("y" if kindN == "xy" else "Latitude (deg)")
    axes[1].imshow(np.ma.masked_invalid(N_masked), origin=origin, extent=extent, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    axes[1].set_title("NALCMS Daymet 1 km PCT_LAKE")
    axes[1].set_xlabel("x" if kindN == "xy" else "Longitude (deg)")
    axes[1].set_ylabel("y" if kindN == "xy" else "Latitude (deg)")
    cbar = fig.colorbar(im0, ax=axes.ravel().tolist(), shrink=0.9)
    cbar.set_label(args.var)
    fig.savefig(maps_file, dpi=200)
    plt.close(fig)

    # Difference
    diff = N_plot - L_plot
    _, _, diff_plot = downsample_for_plot(xN_grid, yN_grid, diff)
    if args.scale == "robust":
        dlim = float(np.nanpercentile(np.abs(diff_plot.ravel()), 98))
    else:
        dlim = float(args.diff_lim)
    diff_or, _, _ = prepare_imshow(diff_plot, xN_ds, yN_ds)
    diff_masked = np.where(mask_or, diff_or, np.nan)
    diffs_file = args.outdir / "pct_lake_lulc2020_vs_nalcms_diffs.png"
    fig2, ax2 = plt.subplots(1, 1, figsize=(8, 6), constrained_layout=True)
    ax2.set_facecolor("white")
    imd = ax2.imshow(np.ma.masked_invalid(diff_masked), origin=origin, extent=extent, cmap=make_cmap("coolwarm"), vmin=-dlim, vmax=dlim, interpolation="nearest")
    ax2.set_title("NALCMS - LULC2020 (PCT_LAKE)")
    ax2.set_xlabel("x" if kindN == "xy" else "Longitude (deg)")
    ax2.set_ylabel("y" if kindN == "xy" else "Latitude (deg)")
    cbar2 = fig2.colorbar(imd, ax=ax2, shrink=0.9)
    cbar2.set_label("Difference")
    fig2.savefig(diffs_file, dpi=200)
    plt.close(fig2)

    print(f"Wrote {maps_file}")
    print(f"Wrote {diffs_file}")


if __name__ == "__main__":
    main()

