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

def compute_stride_for_plot(ny: int, nx: int, max_points: int = 1_000_000) -> int:
    if nx * ny > max_points:
        return max(1, int(np.ceil(np.sqrt((nx * ny) / max_points))))
    return 1

def nearest_idx_1d(vals: np.ndarray, grid: np.ndarray) -> np.ndarray:
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
        return (g.size - 1) - out


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
    x_da = None
    y_da = None
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
    parser = argparse.ArgumentParser(description="Compare LULC 2020 1km PCT_* (lake/glacier/natveg/urban) to NALCMS surfdata Daymet 1km counterparts.")
    parser.add_argument("--lulc-dir", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/references/LULC"))
    parser.add_argument("--nalcms-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c251230.subset.nc"))
    parser.add_argument("--vars", type=str, nargs="+", default=["PCT_LAKE", "PCT_GLACIER", "PCT_NATVEG", "PCT_URBAN"])
    parser.add_argument("--outdir", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/lulc_2020_compare"))
    parser.add_argument("--scale", choices=["robust", "fixed"], default="fixed")
    parser.add_argument("--map-min", type=float, default=0.0)
    parser.add_argument("--map-max", type=float, default=100.0)
    parser.add_argument("--diff-lim", type=float, default=100.0)
    parser.add_argument("--max-points", type=int, default=1_000_000,
                        help="Approximate max pixels for plotting tiles (controls downsampling stride).")
    parser.add_argument("--urban-mode", choices=["stream", "load"], default="stream",
                        help="How to handle LULC PCT_URBAN mapping: 'stream' for low-RAM row streaming; 'load' to load once and gather (faster, higher RAM).")
    parser.add_argument("--urban-per-layer", action="store_true", default=False,
                        help="If set, split PCT_URBAN into three layers and process each layer as a separate 2D variable.")
    parser.add_argument("--urban-layer-map", type=str, default="",
                        help="Optional layer mapping for PCT_URBAN per-layer mode, format 'L:i->N:j' pairs like '0:0,1:1,2:0'. Defaults to identity if omitted.")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    dsN = load_dataset(args.nalcms_file)
    latN, lonN = get_lat_lon_from_ds(dsN)
    xN_grid, yN_grid, kindN = get_plot_grid_from_ds(dsN, "xy")

    # Default LULC filenames per variable
    default_files = {
        "PCT_LAKE": "PCT_LAKE_2020_1k_c230606.nc",
        "PCT_GLACIER": "PCT_GLACIER_2020_1k_c230606.nc",
        "PCT_NATVEG": "PCT_NATVEG_2020_1k_c230606.nc",
        "PCT_URBAN": "PCT_URBAN_2020_1k_c230606.nc",
    }

    def load_lulc_var(var_name: str, load_data: bool = True):
        f = args.lulc_dir / default_files.get(var_name, "")
        if not f.exists():
            raise SystemExit(f"Missing LULC file for {var_name}: {f}")
        dsL = load_dataset(f)
        if var_name not in dsL.data_vars:
            raise SystemExit(f"{var_name} not found in {f}")
        latL, lonL = get_lat_lon_from_ds(dsL)
        arr = dsL[var_name].astype(np.float64).values if load_data else None
        return dsL, latL, lonL, arr

    for v in args.vars:
        # Avoid loading huge arrays for urban
        if v == "PCT_URBAN":
            dsL, latL, lonL, vL = load_lulc_var(v, load_data=False)
            vN = None
        else:
            dsL, latL, lonL, vL = load_lulc_var(v, load_data=True)
            vN = dsN[v].astype(np.float64).values if v in dsN.data_vars else None
        if v not in dsN.data_vars:
            print(f"Skipping {v}: not found in NALCMS dataset.")
            continue

        # For urban, compare totals: sum across the categorical axis (handles numurbl or density_class etc.)
        def totalize_if_needed(a: np.ndarray, varname: str, ds: xr.Dataset) -> np.ndarray:
            if varname != "PCT_URBAN":
                return a
            dims = list(ds[varname].dims)
            # Known categorical dim names
            cat_candidates = {"numurbl", "density_class", "urban_class", "urbl"}
            # Common spatial dim name hints
            spatial_hints = {"lsmlat", "lsmlon", "lat", "lon", "LATIXY", "LONGXY", "y", "x", "YC", "XC"}
            cat_axis = None
            # Prefer known category names
            for i, d in enumerate(dims):
                if d in cat_candidates:
                    cat_axis = i
                    break
            # Fallback: pick the first non-spatial axis if any
            if cat_axis is None and len(dims) > 2:
                for i, d in enumerate(dims):
                    if d not in spatial_hints:
                        cat_axis = i
                        break
            if cat_axis is not None and a.ndim > 2:
                return np.nansum(a, axis=cat_axis)
            return a

        if v == "PCT_URBAN":
            # Per-layer path: handle each 2D layer independently (like lake/glacier)
            if args.urban_per_layer:
                # Category dimension names
                dimsL = list(dsL["PCT_URBAN"].dims)
                cat_dim_L = None
                for d in dimsL:
                    if d in {"density_class", "numurbl", "urban_class", "urbl"}:
                        cat_dim_L = d
                        break
                if cat_dim_L is None and len(dimsL) > 2:
                    cat_dim_L = dimsL[0]
                dimsN = list(dsN["PCT_URBAN"].dims)
                cat_dim_N = None
                for d in dimsN:
                    if d in {"density_class", "numurbl", "urban_class", "urbl"}:
                        cat_dim_N = d
                        break
                if cat_dim_N is None and len(dimsN) > 2:
                    cat_dim_N = dimsN[0]
                # Parse optional mapping L->N (identity by default)
                layer_map: dict[int, int] = {}
                if args.urban_layer_map:
                    try:
                        pairs = [p.strip() for p in args.urban_layer_map.split(",") if p.strip()]
                        for p in pairs:
                            left, right = p.split(":")
                            layer_map[int(left)] = int(right)
                    except Exception:
                        print("Warning: could not parse --urban-layer-map; falling back to identity mapping.")
                        layer_map = {}
                # Fill/missing masks
                fvL = dsL["PCT_URBAN"].attrs.get("_FillValue", dsL["PCT_URBAN"].encoding.get("_FillValue", None))
                mvL = dsL["PCT_URBAN"].attrs.get("missing_value", None)
                # Use Daymet x/y plotting grid
                xN_grid, yN_grid, kindN = get_plot_grid_from_ds(dsN, "xy")
                # Iterate first 3 layers (or available)
                n_layers = min(3, dsL["PCT_URBAN"].sizes.get(cat_dim_L, 3))
                for i in range(n_layers):
                    # Determine which NALCMS layer to compare against
                    j = layer_map.get(i, i)
                    # Clamp to available range
                    if cat_dim_N in dsN["PCT_URBAN"].dims:
                        j = max(0, min(j, dsN["PCT_URBAN"].sizes.get(cat_dim_N, j)))
                    # Extract 2D layers and mask fills
                    L2 = dsL["PCT_URBAN"].isel({cat_dim_L: i}).astype(np.float64).values
                    if fvL is not None:
                        L2 = np.where(L2 == float(fvL), np.nan, L2)
                    if mvL is not None:
                        L2 = np.where(L2 == float(mvL), np.nan, L2)
                    if cat_dim_N is not None and cat_dim_N in dsN["PCT_URBAN"].dims:
                        N2_da = dsN["PCT_URBAN"].isel({cat_dim_N: j}).astype(np.float64)
                    else:
                        N2_da = dsN["PCT_URBAN"].astype(np.float64)
                    N2 = N2_da.values
                    # Map LULC layer to Daymet grid (nearest on regular lat/lon)
                    try:
                        latL1d = dsL.coords["lat"].values
                        lonL1d = dsL.coords["lon"].values
                        L_on_N = nearest_on_regular_lonlat(latL1d, lonL1d, L2, latN, lonN)
                    except Exception:
                        L_on_N = nearest_regrid_to_target(latL, lonL, L2, latN, lonN)
                    # Downsample for plotting
                    xN_ds, yN_ds, L_plot = downsample_for_plot(xN_grid, yN_grid, L_on_N)
                    _, _, N_plot = downsample_for_plot(xN_grid, yN_grid, N2)
                    # Domain mask using lon/lat
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
                    maps_file = args.outdir / f"pct_urban_layer{i}_lulc2020_vs_nalcms_maps.png"
                    fig, axes = plt.subplots(1, 2, figsize=(12, 6), constrained_layout=True)
                    for ax in axes:
                        ax.set_facecolor("white")
                    cmap = make_cmap("viridis")
                    L_masked = np.where(mask_or, L_or, np.nan)
                    N_masked = np.where(mask_or, N_or, np.nan)
                    im0 = axes[0].imshow(np.ma.masked_invalid(L_masked), origin=origin, extent=extent, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
                    axes[0].set_title(f"LULC 2020 PCT_URBAN layer {i} (on Daymet grid)")
                    axes[0].set_xlabel("x" if kindN == "xy" else "Longitude (deg)")
                    axes[0].set_ylabel("y" if kindN == "xy" else "Latitude (deg)")
                    axes[1].imshow(np.ma.masked_invalid(N_masked), origin=origin, extent=extent, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
                    axes[1].set_title(f"NALCMS Daymet 1 km PCT_URBAN layer {j}")
                    axes[1].set_xlabel("x" if kindN == "xy" else "Longitude (deg)")
                    axes[1].set_ylabel("y" if kindN == "xy" else "Latitude (deg)")
                    cbar = fig.colorbar(im0, ax=axes.ravel().tolist(), shrink=0.9)
                    cbar.set_label("PCT_URBAN")
                    fig.savefig(maps_file, dpi=200)
                    plt.close(fig)
                    # Diffs
                    diff = N_plot - L_plot
                    _, _, diff_plot = downsample_for_plot(xN_grid, yN_grid, diff)
                    if args.scale == "robust":
                        dlim = float(np.nanpercentile(np.abs(diff_plot.ravel()), 98))
                    else:
                        dlim = float(args.diff_lim)
                    diff_or, _, _ = prepare_imshow(diff_plot, xN_ds, yN_ds)
                    diff_masked = np.where(mask_or, diff_or, np.nan)
                    diffs_file = args.outdir / f"pct_urban_layer{i}_lulc2020_vs_nalcms_diffs.png"
                    fig2, ax2 = plt.subplots(1, 1, figsize=(8, 6), constrained_layout=True)
                    ax2.set_facecolor("white")
                    imd = ax2.imshow(np.ma.masked_invalid(diff_masked), origin=origin, extent=extent, cmap=make_cmap("coolwarm"), vmin=-dlim, vmax=dlim, interpolation="nearest")
                    ax2.set_title(f"NALCMS layer {j} - LULC2020 layer {i} (PCT_URBAN)")
                    ax2.set_xlabel("x" if kindN == "xy" else "Longitude (deg)")
                    ax2.set_ylabel("y" if kindN == "xy" else "Latitude (deg)")
                    cbar2 = fig2.colorbar(imd, ax=ax2, shrink=0.9)
                    cbar2.set_label("Difference")
                    fig2.savefig(diffs_file, dpi=200)
                    plt.close(fig2)
                    print(f"Wrote {maps_file}")
                    print(f"Wrote {diffs_file}")
                # Done per-layer; continue to next var
                continue

            import time
            t0 = time.perf_counter()
            # Two paths: 'load' (fast, high RAM) or 'stream' (low RAM)
            ny, nx = latN.shape
            stride = compute_stride_for_plot(ny, nx, max_points=args.max_points)
            # Downsample Daymet lon/lat and x/y
            lonN_ds = lonN[::stride, ::stride]
            latN_ds = latN[::stride, ::stride]
            xN_ds = xN_grid[::stride, ::stride]
            yN_ds = yN_grid[::stride, ::stride]
            # Compute nearest indices from Daymet DS -> LULC 1D
            latL1d = dsL.coords["lat"].values
            lonL1d = dsL.coords["lon"].values
            iy_map = nearest_idx_1d(latN_ds, latL1d)
            ix_map = nearest_idx_1d(lonN_ds, lonL1d)
            print(f"[urban] stride={stride}, ds_shape={latN_ds.shape}")
            dimsL = list(dsL["PCT_URBAN"].dims)
            # Identify category, lat, lon dims
            cat_dim_L = None
            for d in dimsL:
                if d in {"density_class", "numurbl", "urban_class", "urbl"}:
                    cat_dim_L = d
                    break
            if cat_dim_L is None and len(dimsL) > 2:
                cat_dim_L = dimsL[0]
            lat_dim_L = "lat" if "lat" in dimsL else dimsL[1]
            lon_dim_L = "lon" if "lon" in dimsL else dimsL[2]
            # Detect fill/missing
            fv = dsL["PCT_URBAN"].attrs.get("_FillValue", dsL["PCT_URBAN"].encoding.get("_FillValue", None))
            mv = dsL["PCT_URBAN"].attrs.get("missing_value", None)
            # Output tile
            L_plot = np.full(latN_ds.shape, np.nan, dtype=np.float32)
            if args.urban_mode == "load":
                # Load once -> sum categories -> vectorized gather
                vL_tot = dsL["PCT_URBAN"].astype(np.float32)
                if fv is not None:
                    vL_tot = vL_tot.where(vL_tot != float(fv))
                if mv is not None:
                    vL_tot = vL_tot.where(vL_tot != float(mv))
                vL_tot = vL_tot.sum(cat_dim_L, skipna=True).values  # 2D
                L_plot = vL_tot[iy_map, ix_map]
            else:
                # Stream one contiguous slab per Daymet row
                unique_rows = np.unique(iy_map)
                for idx, iy_val in enumerate(unique_rows):
                    mask_row = (iy_map == iy_val)
                    if not np.any(mask_row):
                        continue
                    min_ix = int(np.min(ix_map[mask_row]))
                    max_ix = int(np.max(ix_map[mask_row])) + 1
                    slab = dsL["PCT_URBAN"].isel({lat_dim_L: iy_val, lon_dim_L: slice(min_ix, max_ix)}).astype(np.float32)
                    if fv is not None:
                        slab = slab.where(slab != float(fv))
                    if mv is not None:
                        slab = slab.where(slab != float(mv))
                    slab_sum = slab.sum(cat_dim_L, skipna=True).values  # shape (max_ix-min_ix,)
                    sel_cols = ix_map[mask_row] - min_ix
                    L_plot[mask_row] = slab_sum[sel_cols]
                    if (idx % max(1, (len(unique_rows)//25 or 1))) == 0:
                        print(f"[urban] row {idx+1}/{len(unique_rows)}")
            # NALCMS total (float32) and stride
            if "numurbl" in dsN["PCT_URBAN"].dims:
                daN_tot = dsN["PCT_URBAN"].astype(np.float32).sum("numurbl")
            else:
                d0 = list(dsN["PCT_URBAN"].dims)[0]
                daN_tot = dsN["PCT_URBAN"].astype(np.float32).sum(d0)
            N_plot = daN_tot.isel(y=slice(0, None, stride), x=slice(0, None, stride)).values
            print(f"[urban] total elapsed {time.perf_counter()-t0:.2f}s")
        else:
            # Non-urban variables: original path
            vL_eff = totalize_if_needed(vL, v, dsL)
            vN_eff = totalize_if_needed(vN, v, dsN)
            try:
                latL1d = dsL.coords["lat"].values
                lonL1d = dsL.coords["lon"].values
                L_on_N = nearest_on_regular_lonlat(latL1d, lonL1d, vL_eff, latN, lonN)
            except Exception:
                L_on_N = nearest_regrid_to_target(latL, lonL, vL_eff, latN, lonN)
            xN_ds, yN_ds, L_plot = downsample_for_plot(xN_grid, yN_grid, L_on_N)
            _, _, N_plot = downsample_for_plot(xN_grid, yN_grid, vN_eff)

        # Domain mask from Daymet lon/lat
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
        maps_file = args.outdir / f"{v.lower()}_lulc2020_vs_nalcms_maps.png"
        fig, axes = plt.subplots(1, 2, figsize=(12, 6), constrained_layout=True)
        for ax in axes:
            ax.set_facecolor("white")
        cmap = make_cmap("viridis")
        L_masked = np.where(mask_or, L_or, np.nan)
        N_masked = np.where(mask_or, N_or, np.nan)
        im0 = axes[0].imshow(np.ma.masked_invalid(L_masked), origin=origin, extent=extent, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
        axes[0].set_title(f"LULC 2020 {v} (on Daymet grid)")
        axes[0].set_xlabel("x" if kindN == "xy" else "Longitude (deg)")
        axes[0].set_ylabel("y" if kindN == "xy" else "Latitude (deg)")
        axes[1].imshow(np.ma.masked_invalid(N_masked), origin=origin, extent=extent, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
        axes[1].set_title(f"NALCMS Daymet 1 km {v}")
        axes[1].set_xlabel("x" if kindN == "xy" else "Longitude (deg)")
        axes[1].set_ylabel("y" if kindN == "xy" else "Latitude (deg)")
        cbar = fig.colorbar(im0, ax=axes.ravel().tolist(), shrink=0.9)
        cbar.set_label(v)
        fig.savefig(maps_file, dpi=200)
        plt.close(fig)

        # Differences
        diff = N_plot - L_plot
        _, _, diff_plot = downsample_for_plot(xN_grid, yN_grid, diff)
        if args.scale == "robust":
            dlim = float(np.nanpercentile(np.abs(diff_plot.ravel()), 98))
        else:
            dlim = float(args.diff_lim)
        diff_or, _, _ = prepare_imshow(diff_plot, xN_ds, yN_ds)
        diff_masked = np.where(mask_or, diff_or, np.nan)
        diffs_file = args.outdir / f"{v.lower()}_lulc2020_vs_nalcms_diffs.png"
        fig2, ax2 = plt.subplots(1, 1, figsize=(8, 6), constrained_layout=True)
        ax2.set_facecolor("white")
        imd = ax2.imshow(np.ma.masked_invalid(diff_masked), origin=origin, extent=extent, cmap=make_cmap("coolwarm"), vmin=-dlim, vmax=dlim, interpolation="nearest")
        ax2.set_title(f"NALCMS - LULC2020 ({v})")
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

