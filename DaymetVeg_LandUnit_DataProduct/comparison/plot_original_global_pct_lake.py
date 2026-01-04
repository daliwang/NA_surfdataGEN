import argparse
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt


def to_minus180_180(lon):
    lon = np.asarray(lon, dtype=float)
    lon = np.mod(lon + 180.0, 360.0) - 180.0
    return lon


def make_cmap(name: str):
    cmap = plt.get_cmap(name).copy()
    cmap.set_bad(color=(0.0, 0.0, 0.0, 0.0))  # transparent NaNs
    return cmap


def prepare_imshow(z, lon_grid, lat_grid):
    lon = lon_grid
    lat = lat_grid
    z_plot = z
    # Flip L/R if longitudes decrease left->right
    try:
        lon_left = np.nanmean(lon[:, 0])
        lon_right = np.nanmean(lon[:, -1])
        if np.isfinite(lon_left) and np.isfinite(lon_right) and lon_left > lon_right:
            z_plot = np.fliplr(z_plot)
            lon = np.fliplr(lon)
    except Exception:
        pass
    # Choose origin based on latitude orientation
    origin = "lower"
    try:
        lat_top = np.nanmean(lat[0, :])
        lat_bottom = np.nanmean(lat[-1, :])
        if np.isfinite(lat_top) and np.isfinite(lat_bottom) and lat_top > lat_bottom:
            origin = "upper"
    except Exception:
        origin = "lower"
    extent = [float(np.nanmin(lon)), float(np.nanmax(lon)), float(np.nanmin(lat)), float(np.nanmax(lat))]
    return z_plot, extent, origin


def main():
    parser = argparse.ArgumentParser(description="Plot original 0.5° PCT_LAKE over the Daymet region (no interpolation).")
    parser.add_argument("--global-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/references/surfdata_0.5x0.5_simyr1850_c200609_with_TOP.nc"))
    parser.add_argument("--daymet-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/surfdata.Daymet_NA.1km.2d.c250625.subset.nc"))
    parser.add_argument("--out", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/pct_lake_global_region.png"))
    parser.add_argument("--var", type=str, default="PCT_LAKE", help="Variable to plot from global/daymet (iPCT_LAKE aliases to PCT_LAKE).")
    parser.add_argument("--global-mask-var", type=str, default="PFTDATA_MASK",
                        help="Mask variable name in the global file; cells with mask==0 will not be plotted.")
    parser.add_argument("--scale", choices=["robust", "fixed"], default="fixed")
    parser.add_argument("--map-min", type=float, default=0.0)
    parser.add_argument("--map-max", type=float, default=100.0)
    args = parser.parse_args()

    var_name = "PCT_LAKE" if args.var == "iPCT_LAKE" else args.var

    dsG = xr.open_dataset(args.global_file)
    dsD = xr.open_dataset(args.daymet_file)

    # Pull lat/lon
    latG = dsG["LATIXY"].values
    lonG = to_minus180_180(dsG["LONGXY"].values)
    latD = dsD["LATIXY"].values
    lonD = to_minus180_180(dsD["LONGXY"].values)

    # Region bounds from Daymet lat/lon (ensure in [-180,180])
    lat_min = float(np.nanmin(latD))
    lat_max = float(np.nanmax(latD))
    lon_min = float(np.nanmin(lonD))
    lon_max = float(np.nanmax(lonD))

    # Variable data
    if var_name not in dsG.variables:
        raise SystemExit(f"{var_name} not found in global file.")
    if var_name not in dsD.variables:
        raise SystemExit(f"{var_name} not found in daymet file.")
    gvar = dsG[var_name].astype(np.float64).values
    dvar = dsD[var_name].astype(np.float64).values
    # Detect and honor _FillValue/missing_value if any (xarray usually decodes to NaN, this is defensive)
    fv = dsG[var_name].attrs.get("_FillValue", None)
    mv = dsG[var_name].attrs.get("missing_value", None)
    if fv is not None:
        gvar = np.where(gvar == fv, np.nan, gvar)
    if mv is not None:
        gvar = np.where(gvar == mv, np.nan, gvar)

    # Build rectilinear 1D coordinates from global grid (raw 0.5° centers in [-180,180])
    lonG_1d = np.nanmean(lonG, axis=0)
    latG_1d = np.nanmean(latG, axis=1)
    # Select index ranges inside Daymet bbox (no interpolation)
    ilon = (lonG_1d >= lon_min) & (lonG_1d <= lon_max)
    ilat = (latG_1d >= lat_min) & (latG_1d <= lat_max)
    if not np.any(ilon):
        ilon = np.ones_like(lonG_1d, dtype=bool)
    if not np.any(ilat):
        ilat = np.ones_like(latG_1d, dtype=bool)
    lon_sel = lonG_1d[ilon]
    lat_sel = latG_1d[ilat]
    gvar_sel = gvar[np.ix_(ilat, ilon)]
    # Apply native mask variable if provided/available
    if args.global_mask_var:
        if args.global_mask_var in dsG.variables:
            m = dsG[args.global_mask_var].values
            # Try to broadcast to 2D if mask has extra dims
            while m.ndim > 2:
                m = m[0]
            mask_sel = m[np.ix_(ilat, ilon)]
            gvar_sel = np.where(mask_sel == 0, np.nan, gvar_sel)
        else:
            print(f"Warning: mask variable {args.global_mask_var} not found; proceeding without it.")
    else:
        # Auto-detect a common mask if present
        for auto_var in ("PFTDATA_MASK", "PFTDATA_MASKS", "LANDFRAC_PFT"):
            if auto_var in dsG.variables:
                m = dsG[auto_var].values
                while m.ndim > 2:
                    m = m[0]
                mask_sel = m[np.ix_(ilat, ilon)]
                # For LANDFRAC_PFT use >0 as valid
                if auto_var == "LANDFRAC_PFT":
                    gvar_sel = np.where(mask_sel <= 0, np.nan, gvar_sel)
                else:
                    gvar_sel = np.where(mask_sel == 0, np.nan, gvar_sel)
                break

    # Downsample Daymet a bit for plotting efficiency
    def downsample(x, y, z, max_points=1_000_000):
        ny, nx = z.shape
        if nx * ny > max_points:
            stride = max(1, int(np.ceil(np.sqrt((nx * ny) / max_points))))
        else:
            stride = 1
        return x[::stride, ::stride], y[::stride, ::stride], z[::stride, ::stride]

    lonD_ds, latD_ds, dvar_ds = downsample(lonD, latD, dvar)

    # Color limits
    if args.scale == "robust":
        vmin = float(np.nanpercentile(gvar_sub.ravel(), 2))
        vmax = float(np.nanpercentile(gvar_sub.ravel(), 98))
        # include daymet in scale for side-by-side consistency
        d2 = dvar_ds.ravel()
        vmin = float(np.nanmin([vmin, np.nanpercentile(d2, 2)]))
        vmax = float(np.nanmax([vmax, np.nanpercentile(d2, 98)]))
    else:
        vmin = args.map_min
        vmax = args.map_max

    # Prepare extent for global using 1D coords (both in [-180,180])
    g_ext = [float(np.nanmin(lon_sel)), float(np.nanmax(lon_sel)),
             float(np.nanmin(lat_sel)), float(np.nanmax(lat_sel))]
    d_plot, d_ext, d_org = prepare_imshow(dvar_ds, lonD_ds, latD_ds)

    # Domain mask for global selection is simply the selected index window; keep NaNs transparent
    maskG_plot = np.ones_like(gvar_sel, dtype=bool)
    maskD = np.isfinite(lonD_ds) & np.isfinite(latD_ds)
    maskD_plot, _, _ = prepare_imshow(maskD.astype(float), lonD_ds, latD_ds)
    maskD_plot = maskD_plot > 0.5

    cmap = make_cmap("viridis")
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    axes[0].set_facecolor("white")
    axes[1].set_facecolor("white")
    axes[0].set_title("Global 0.5° (original, bbox = Daymet region)")
    axes[1].set_title("Daymet 1 km")
    # Plot raw 0.5° without interpolation using pcolormesh over chosen bbox
    im0 = axes[0].pcolormesh(lon_sel, lat_sel, np.ma.masked_invalid(np.where(maskG_plot, gvar_sel, np.nan)),
                             shading="nearest", cmap=cmap, vmin=vmin, vmax=vmax)
    axes[0].set_xlabel("Longitude (deg)")
    axes[0].set_ylabel("Latitude (deg)")
    axes[1].imshow(np.ma.masked_invalid(np.where(maskD_plot, d_plot, np.nan)), origin=d_org, extent=d_ext, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    axes[1].set_xlabel("Longitude (deg)")
    axes[1].set_ylabel("Latitude (deg)")
    # Match x-limits to the Daymet display range/bbox
    try:
        x_min = lon_min
        x_max = lon_max
        axes[0].set_xlim(x_min, x_max)
        axes[1].set_xlim(x_min, x_max)
    except Exception:
        pass
    cbar = fig.colorbar(im0, ax=axes.ravel().tolist(), shrink=0.9)
    cbar.set_label(var_name)
    fig.savefig(args.out, dpi=200)
    plt.close(fig)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()


