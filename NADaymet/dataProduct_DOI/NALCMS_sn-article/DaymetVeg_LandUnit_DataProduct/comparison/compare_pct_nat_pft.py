import argparse
import os
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
        dists, nn = tree.query(np.column_stack((lat_tgt_flat[idxs], lon_tgt_flat[idxs])), k=1)
        regrid_flat[idxs] = data_src_f[nn]
    regrid = regrid_flat.reshape(tgt_shape)
    return regrid


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
    parser = argparse.ArgumentParser(description="Compare PCT_NAT_PFT across three surfdata datasets (Global-like, Daymet 1km, NALCMS 1km).")
    parser.add_argument("--global-pft-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/landuse.PCT_NAT_PFT_last.nc"))
    parser.add_argument("--daymet-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/surfdata.Daymet_NA.1km.2d.c250625.subset.nc"))
    parser.add_argument("--nalcms-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c251230.nc"))
    parser.add_argument("--outdir", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/pct_nat_pft_compare_landuse"))
    parser.add_argument("--pft-start", type=int, default=0)
    parser.add_argument("--pft-end", type=int, default=16)
    parser.add_argument("--scale", choices=["robust", "fixed"], default="fixed")
    parser.add_argument("--map-min", type=float, default=0.0)
    parser.add_argument("--map-max", type=float, default=100.0)
    parser.add_argument("--diff-lim", type=float, default=100.0)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    dsA = load_dataset(args.global_pft_file)
    dsB = load_dataset(args.daymet_file)
    dsC = load_dataset(args.nalcms_file)

    if "PCT_NAT_PFT" not in dsA.variables:
        raise SystemExit("PCT_NAT_PFT not found in global PFT file.")
    if "PCT_NAT_PFT" not in dsB.variables or "PCT_NAT_PFT" not in dsC.variables:
        raise SystemExit("PCT_NAT_PFT not found in one or both 1 km datasets.")

    latA, lonA = get_lat_lon_from_ds(dsA)
    latB, lonB = get_lat_lon_from_ds(dsB)
    latC, lonC = get_lat_lon_from_ds(dsC)

    xB_grid, yB_grid, _ = get_plot_grid_from_ds(dsB, "xy")
    xC_grid, yC_grid, _ = get_plot_grid_from_ds(dsC, "xy")

    cmap = make_cmap("viridis")
    for i in range(args.pft_start, args.pft_end + 1):
        daA_i = dsA["PCT_NAT_PFT"].isel(natpft=i).astype(np.float64)
        daB_i = dsB["PCT_NAT_PFT"].isel(natpft=i).astype(np.float64) if "natpft" in dsB["PCT_NAT_PFT"].dims else dsB["PCT_NAT_PFT"].astype(np.float64)
        daC_i = dsC["PCT_NAT_PFT"].isel(natpft=i).astype(np.float64) if "natpft" in dsC["PCT_NAT_PFT"].dims else dsC["PCT_NAT_PFT"].astype(np.float64)

        A_on_B = nearest_regrid_to_target(latA, lonA, daA_i.values, latB, lonB)
        xB_ds, yB_ds, AonB_plot = downsample_for_plot(xB_grid, yB_grid, A_on_B)
        _, _, B_plot = downsample_for_plot(xB_grid, yB_grid, daB_i.values)
        xC_ds, yC_ds, C_plot = downsample_for_plot(xC_grid, yC_grid, daC_i.values)

        lonB_ds, latB_ds, _ = downsample_for_plot(lonB, latB, A_on_B)
        lonC_ds, latC_ds, _ = downsample_for_plot(lonC, latC, daC_i.values)
        maskB_domain = np.isfinite(lonB_ds) & np.isfinite(latB_ds)
        maskC_domain = np.isfinite(lonC_ds) & np.isfinite(latC_ds)

        if args.scale == "robust":
            vals = np.concatenate([AonB_plot.ravel(), B_plot.ravel(), C_plot.ravel()])
            vmin = float(np.nanpercentile(vals, 2))
            vmax = float(np.nanpercentile(vals, 98))
        else:
            vmin = args.map_min
            vmax = args.map_max

        AonB_or, extent_B, origin_B = prepare_imshow(AonB_plot, xB_ds, yB_ds)
        B_or, _, _ = prepare_imshow(B_plot, xB_ds, yB_ds)
        C_or, extent_C, origin_C = prepare_imshow(C_plot, xC_ds, yC_ds)
        maskB_or, _, _ = prepare_imshow(maskB_domain.astype(float), xB_ds, yB_ds)
        maskB_or = maskB_or > 0.5
        maskC_or, _, _ = prepare_imshow(maskC_domain.astype(float), xC_ds, yC_ds)
        maskC_or = maskC_or > 0.5

        maps_file = args.outdir / f"pct_nat_pft_pft{i}_maps.png"
        fig, axes = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
        for ax in axes:
            ax.set_facecolor("white")
        A_masked = np.where(maskB_or, AonB_or, np.nan)
        B_masked = np.where(maskB_or, B_or, np.nan)
        C_masked = np.where(maskC_or, C_or, np.nan)
        im = axes[0].imshow(np.ma.masked_invalid(A_masked), origin=origin_B, extent=extent_B, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
        axes[0].set_title(f"Global_2016 PFT{i}")
        axes[0].set_xlabel("x")
        axes[0].set_ylabel("y")
        axes[1].imshow(np.ma.masked_invalid(B_masked), origin=origin_B, extent=extent_B, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
        axes[1].set_title(f"Global_1850 PFT{i}")
        axes[1].set_xlabel("x")
        axes[1].set_ylabel("y")
        axes[2].imshow(np.ma.masked_invalid(C_masked), origin=origin_C, extent=extent_C, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
        axes[2].set_title(f"NALCMS_2020 PFT{i}")
        axes[2].set_xlabel("x")
        axes[2].set_ylabel("y")
        cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.9)
        cbar.set_label("PCT_NAT_PFT")
        fig.savefig(maps_file, dpi=200)
        plt.close(fig)

        diff_BA = daB_i.values - A_on_B
        diff_CA = daC_i.values - A_on_B
        diff_CB = daC_i.values - daB_i.values
        _, _, diff_BA_plot = downsample_for_plot(xB_grid, yB_grid, diff_BA)
        _, _, diff_CA_plot = downsample_for_plot(xB_grid, yB_grid, diff_CA)
        _, _, diff_CB_plot = downsample_for_plot(xB_grid, yB_grid, diff_CB)
        if args.scale == "robust":
            dlim = float(np.nanpercentile(np.abs(np.concatenate([diff_BA_plot.ravel(), diff_CA_plot.ravel(), diff_CB_plot.ravel()])), 98))
        else:
            dlim = float(args.diff_lim)
        diff_BA_or, _, _ = prepare_imshow(diff_BA_plot, xB_ds, yB_ds)
        diff_CA_or, _, _ = prepare_imshow(diff_CA_plot, xB_ds, yB_ds)
        diff_CB_or, _, _ = prepare_imshow(diff_CB_plot, xB_ds, yB_ds)
        diff_BA_masked = np.where(maskB_or, diff_BA_or, np.nan)
        diff_CA_masked = np.where(maskB_or, diff_CA_or, np.nan)
        diff_CB_masked = np.where(maskB_or, diff_CB_or, np.nan)

        diffs_file = args.outdir / f"pct_nat_pft_pft{i}_diffs.png"
        fig2, axes2 = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
        for ax in axes2:
            ax.set_facecolor("white")
        cmap_diff = make_cmap("coolwarm")
        im2 = axes2[0].imshow(np.ma.masked_invalid(diff_BA_masked), origin=origin_B, extent=extent_B, cmap=cmap_diff, vmin=-dlim, vmax=dlim, interpolation="nearest")
        axes2[0].set_title(f"Global_1850 - Global_2016 PFT{i}")
        axes2[0].set_xlabel("x")
        axes2[0].set_ylabel("y")
        axes2[1].imshow(np.ma.masked_invalid(diff_CA_masked), origin=origin_B, extent=extent_B, cmap=cmap_diff, vmin=-dlim, vmax=dlim, interpolation="nearest")
        axes2[1].set_title(f"NALCMS_2020 - Global_2016 PFT{i}")
        axes2[1].set_xlabel("x")
        axes2[1].set_ylabel("y")
        axes2[2].imshow(np.ma.masked_invalid(diff_CB_masked), origin=origin_B, extent=extent_B, cmap=cmap_diff, vmin=-dlim, vmax=dlim, interpolation="nearest")
        axes2[2].set_title(f"NALCMS_2020 - Global_1850 PFT{i}")
        axes2[2].set_xlabel("x")
        axes2[2].set_ylabel("y")
        cbar2 = fig2.colorbar(im2, ax=axes2.ravel().tolist(), shrink=0.9)
        cbar2.set_label("Difference")
        fig2.savefig(diffs_file, dpi=200)
        plt.close(fig2)

        print(f"Wrote {maps_file}")
        print(f"Wrote {diffs_file}")


if __name__ == "__main__":
    main()

