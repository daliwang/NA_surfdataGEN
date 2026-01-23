import argparse
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree


def normalize_longitude(lon_array: np.ndarray) -> np.ndarray:
    lon = np.asarray(lon_array)
    lon_norm = np.mod(lon, 360.0)
    return lon_norm


def load_dataset(path: Path) -> xr.Dataset:
    return xr.open_dataset(path)


def get_lat_lon_from_ds(ds: xr.Dataset):
    lat_candidates = ["LATIXY", "lat", "latitude", "LAT"]
    lon_candidates = ["LONGXY", "LONG", "lon", "longitude", "LON"]
    lat_da, lon_da = None, None
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
    x_da, y_da = None, None
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


def nearest_regrid_to_target(lat_src, lon_src, data_src, lat_tgt, lon_tgt):
    mask_src = np.isfinite(lat_src) & np.isfinite(lon_src) & np.isfinite(data_src)
    lat_src_f = lat_src[mask_src]
    lon_src_f = lon_src[mask_src]
    data_src_f = data_src[mask_src]
    lon_src_f = normalize_longitude(lon_src_f)
    lon_tgt_f = normalize_longitude(lon_tgt)
    pts_src = np.column_stack((lat_src_f.ravel(), lon_src_f.ravel()))
    tree = cKDTree(pts_src)
    tgt_shape = lat_tgt.shape
    lat_tgt_flat = lat_tgt.ravel()
    lon_tgt_flat = lon_tgt_f.ravel()
    valid_tgt = np.isfinite(lat_tgt_flat) & np.isfinite(lon_tgt_flat)
    regrid_flat = np.full(lat_tgt_flat.shape, np.nan, dtype=data_src_f.dtype)
    idxs = np.where(valid_tgt)[0]
    if idxs.size > 0:
        _, nn = tree.query(np.column_stack((lat_tgt_flat[idxs], lon_tgt_flat[idxs])), k=1)
        regrid_flat[idxs] = data_src_f[nn]
    regrid = regrid_flat.reshape(tgt_shape)
    return regrid


def nearest_on_regular_lonlat(lat1d: np.ndarray, lon1d: np.ndarray, data2d: np.ndarray, lat_tgt: np.ndarray, lon_tgt: np.ndarray) -> np.ndarray:
    lat1d = np.asarray(lat1d).astype(float)
    lon1d = np.asarray(lon1d).astype(float)
    lon_tgt_norm = lon_tgt.copy().astype(float)
    if np.nanmin(lon1d) >= 0.0 and np.nanmax(lon1d) <= 360.0:
        lon_tgt_norm = np.mod(lon_tgt_norm, 360.0)
    else:
        lon_tgt_norm = ((lon_tgt_norm + 180.0) % 360.0) - 180.0
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
            return (g.size - 1) - out
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
    try:
        x_left = np.nanmean(xg[:, 0])
        x_right = np.nanmean(xg[:, -1])
        if np.isfinite(x_left) and np.isfinite(x_right) and x_left > x_right:
            z_plot = np.fliplr(z_plot)
            xg = np.fliplr(xg)
    except Exception:
        pass
    origin = "lower"
    try:
        y_top = np.nanmean(yg[0, :])
        y_bottom = np.nanmean(yg[-1, :])
        if np.isfinite(y_top) and np.isfinite(y_bottom) and y_top > y_bottom:
            origin = "upper"
    except Exception:
        origin = "lower"
    extent = [float(np.nanmin(xg)), float(np.nanmax(xg)), float(np.nanmin(yg)), float(np.nanmax(yg))]
    return z_plot, extent, origin


def make_cmap(name: str):
    cmap = plt.get_cmap(name).copy()
    cmap.set_bad(color=(0.0, 0.0, 0.0, 0.0))
    return cmap


def main():
    parser = argparse.ArgumentParser(description="Compare NALCMS PCT_NAT_PFT (percent per PFT) vs LULC NAT_PFT_INDEX (single PFT per cell).")
    parser.add_argument("--nalcms-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c251230.subset.nc"))
    parser.add_argument("--lulc-index-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/references/LULC/PCT_NAT_PFT_INDEX_2020_1k_c230606.nc"))
    parser.add_argument("--outdir", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/nalcms_vs_lulc_nat_pft"))
    parser.add_argument("--pft-start", type=int, default=0)
    parser.add_argument("--pft-end", type=int, default=16)
    parser.add_argument("--scale", choices=["robust", "fixed"], default="fixed")
    parser.add_argument("--map-min", type=float, default=0.0)
    parser.add_argument("--map-max", type=float, default=100.0)
    parser.add_argument("--diff-lim", type=float, default=100.0)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    dsN = load_dataset(args.nalcms_file)
    dsL = load_dataset(args.lulc_index_file)
    if "PCT_NAT_PFT" not in dsN.data_vars:
        raise SystemExit("PCT_NAT_PFT not found in NALCMS file.")
    if "PCT_NAT_PFT_INDEX" not in dsL.data_vars:
        raise SystemExit("PCT_NAT_PFT_INDEX not found in LULC file.")

    latN, lonN = get_lat_lon_from_ds(dsN)
    xN_grid, yN_grid, kindN = get_plot_grid_from_ds(dsN, "xy")
    latL, lonL = get_lat_lon_from_ds(dsL)

    # Prepare plotting and mask grids
    _, _, lonN_plot = downsample_for_plot(xN_grid, yN_grid, lonN)
    _, _, latN_plot = downsample_for_plot(xN_grid, yN_grid, latN)
    mask_domain = np.isfinite(lonN_plot) & np.isfinite(latN_plot)

    # Read LULC index and masks
    idx = dsL["PCT_NAT_PFT_INDEX"].astype(np.int16).values
    fvL = dsL["PCT_NAT_PFT_INDEX"].attrs.get("_FillValue", dsL["PCT_NAT_PFT_INDEX"].encoding.get("_FillValue", None))
    mvL = dsL["PCT_NAT_PFT_INDEX"].attrs.get("missing_value", None)
    if fvL is not None:
        idx = np.where(idx == int(fvL), -32768, idx)
    if mvL is not None:
        idx = np.where(idx == int(mvL), -32768, idx)  # mark as invalid

    cmap = make_cmap("viridis")
    for pft in range(args.pft_start, args.pft_end + 1):
        # Build 2D percent from categorical index (100 where equals pft, else 0; NaN where invalid)
        L2 = np.where(idx == pft, 100.0, 0.0).astype(np.float32)
        L2 = np.where(idx < 0, np.nan, L2)

        # Map to Daymet/NALCMS grid
        try:
            latL1d = dsL.coords["lat"].values
            lonL1d = dsL.coords["lon"].values
            L_on_N = nearest_on_regular_lonlat(latL1d, lonL1d, L2, latN, lonN)
        except Exception:
            L_on_N = nearest_regrid_to_target(latL, lonL, L2, latN, lonN)

        # Extract NALCMS layer
        N2 = dsN["PCT_NAT_PFT"].isel(natpft=pft).astype(np.float64).values

        # Downsample for plotting
        xN_ds, yN_ds, L_plot = downsample_for_plot(xN_grid, yN_grid, L_on_N)
        _, _, N_plot = downsample_for_plot(xN_grid, yN_grid, N2)

        # Color scaling
        if args.scale == "robust":
            vals = np.concatenate([L_plot.ravel(), N_plot.ravel()])
            vmin = float(np.nanpercentile(vals, 2))
            vmax = float(np.nanpercentile(vals, 98))
        else:
            vmin, vmax = args.map_min, args.map_max

        # Orientation/extent
        L_or, extent, origin = prepare_imshow(L_plot, xN_ds, yN_ds)
        N_or, _, _ = prepare_imshow(N_plot, xN_ds, yN_ds)
        mask_or, _, _ = prepare_imshow(mask_domain.astype(float), xN_ds, yN_ds)
        mask_or = mask_or > 0.5

        # Maps
        maps_file = args.outdir / f"pct_nat_pft_pft{pft}_lulc_vs_nalcms_maps.png"
        fig, axes = plt.subplots(1, 2, figsize=(18, 6), constrained_layout=True)
        for ax in axes:
            ax.set_facecolor("white")
        L_masked = np.where(mask_or, L_or, np.nan)
        N_masked = np.where(mask_or, N_or, np.nan)
        im = axes[0].imshow(np.ma.masked_invalid(L_masked), origin=origin, extent=extent, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
        axes[0].set_title(f"LULC one-hot (PFT={pft}) on Daymet")
        axes[0].set_xlabel("x" if kindN == "xy" else "Longitude (deg)")
        axes[0].set_ylabel("y" if kindN == "xy" else "Latitude (deg)")
        axes[1].imshow(np.ma.masked_invalid(N_masked), origin=origin, extent=extent, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
        axes[1].set_title(f"NALCMS PCT_NAT_PFT (PFT={pft})")
        axes[1].set_xlabel("x" if kindN == "xy" else "Longitude (deg)")
        axes[1].set_ylabel("y" if kindN == "xy" else "Latitude (deg)")
        cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.9)
        cbar.set_label("Percent")
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
        diffs_file = args.outdir / f"pct_nat_pft_pft{pft}_lulc_vs_nalcms_diffs.png"
        fig2, axes2 = plt.subplots(1, 1, figsize=(9, 6), constrained_layout=True)
        axes2.set_facecolor("white")
        im2 = axes2.imshow(np.ma.masked_invalid(diff_masked), origin=origin, extent=extent, cmap=make_cmap("coolwarm"), vmin=-dlim, vmax=dlim, interpolation="nearest")
        axes2.set_title(f"NALCMS - LULC one-hot (PFT={pft})")
        axes2.set_xlabel("x" if kindN == "xy" else "Longitude (deg)")
        axes2.set_ylabel("y" if kindN == "xy" else "Latitude (deg)")
        cbar2 = fig2.colorbar(im2, ax=axes2, shrink=0.9)
        cbar2.set_label("Difference")
        fig2.savefig(diffs_file, dpi=200)
        plt.close(fig2)

        print(f"Wrote {maps_file}")
        print(f"Wrote {diffs_file}")


if __name__ == "__main__":
    main()

