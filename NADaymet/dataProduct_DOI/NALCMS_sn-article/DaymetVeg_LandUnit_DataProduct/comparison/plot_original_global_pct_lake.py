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
    parser = argparse.ArgumentParser(description="Plot original 0.5° variables over the Daymet region (no interpolation), optionally clipped to the Daymet x,y domain.")
    parser.add_argument("--global-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/references/surfdata_0.5x0.5_simyr1850_c200609_with_TOP.nc"))
    parser.add_argument("--daymet-file", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/surfdata.Daymet_NA.1km.2d.c250625.subset.nc"))
    parser.add_argument("--out", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/pct_lake_global_region.png"))
    parser.add_argument("--outdir", type=Path, default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/reference_plot"),
                        help="Directory to write outputs when plotting multiple variables.")
    parser.add_argument("--filename-template", type=str, default="{var}.png",
                        help="Filename template for outputs in --outdir when plotting multiple variables.")
    parser.add_argument("--var", type=str, default="PCT_LAKE", help="Single variable to plot (iPCT_LAKE aliases to PCT_LAKE).")
    parser.add_argument("--vars", type=str, nargs="+", help="Multiple variables to plot.")
    parser.add_argument("--global-mask-var", type=str, default="PFTDATA_MASK",
                        help="Mask variable name in the global file; cells with mask==0 will not be plotted.")
    parser.add_argument("--scale", choices=["robust", "fixed"], default="fixed")
    parser.add_argument("--map-min", type=float, default=0.0)
    parser.add_argument("--map-max", type=float, default=100.0)
    parser.add_argument("--clip-to-daymet-domain", dest="clip_to_daymet_domain", action="store_true", default=True,
                        help="If set, further restrict global cells to where the Daymet x,y grid exists (excludes Hawaii, Caribbean, etc.).")
    parser.add_argument("--no-clip-to-daymet-domain", dest="clip_to_daymet_domain", action="store_false",
                        help="Disable clipping to Daymet domain; only apply Daymet bbox.")
    parser.add_argument("--mask-max-points", type=int, default=300_000,
                        help="Max Daymet points to use when constructing coverage mask (performance control).")
    args = parser.parse_args()

    # Backward-compatibility: if --vars/--all-grid-vars not used, fall back to single variable flow
    def canonical_var(name: str):
        return "PCT_LAKE" if name == "iPCT_LAKE" else name
    var_name = canonical_var(args.var)

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
    # Precompute a global validity mask (from global dataset) on the selected window
    mask_valid_sel = None
    chosen_mask_var = None
    if args.global_mask_var and args.global_mask_var in dsG.variables:
        chosen_mask_var = args.global_mask_var
    else:
        for auto_var in ("PFTDATA_MASK", "PFTDATA_MASKS", "LANDFRAC_PFT"):
            if auto_var in dsG.variables:
                chosen_mask_var = auto_var
                break
    if chosen_mask_var is not None:
        m = dsG[chosen_mask_var].values
        while m.ndim > 2:
            m = m[0]
        m_sel = m[np.ix_(ilat, ilon)]
        if chosen_mask_var == "LANDFRAC_PFT":
            mask_valid_sel = m_sel > 0
        else:
            mask_valid_sel = m_sel != 0

    # Downsample Daymet a bit for plotting efficiency
    def downsample(x, y, z, max_points=1_000_000):
        ny, nx = z.shape
        if nx * ny > max_points:
            stride = max(1, int(np.ceil(np.sqrt((nx * ny) / max_points))))
        else:
            stride = 1
        return x[::stride, ::stride], y[::stride, ::stride], z[::stride, ::stride]

    # Identify and align arrays to lat/lon; support optional single categorical axis expansion
    def reduce_to_latlon_2d(arr, lat_grid, lon_grid):
        a = np.asarray(arr)
        ny, nx = lat_grid.shape
        shape = a.shape
        # Find axes that match lat and lon sizes
        axes_lat = [i for i, d in enumerate(shape) if d == ny]
        axes_lon = [i for i, d in enumerate(shape) if d == nx]
        if not axes_lat or not axes_lon:
            return None
        axis_lat = axes_lat[0]
        # Choose a lon axis different from the chosen lat axis
        axis_lon = None
        for ax in axes_lon:
            if ax != axis_lat:
                axis_lon = ax
                break
        if axis_lon is None:
            return None
        # Move other axes to the front, then reduce (mean) over them
        other_axes = [i for i in range(a.ndim) if i not in (axis_lat, axis_lon)]
        order = other_axes + [axis_lat, axis_lon]
        aT = np.transpose(a, axes=order)
        if other_axes:
            a2d = np.nanmean(aT, axis=tuple(range(len(other_axes))))
        else:
            a2d = aT
        # Ensure final shape matches (ny, nx)
        if a2d.shape != (ny, nx):
            return None
        return a2d
    def expand_to_latlon_stack(arr, lat_grid, lon_grid):
        a = np.asarray(arr)
        ny, nx = lat_grid.shape
        shape = a.shape
        axes_lat = [i for i, d in enumerate(shape) if d == ny]
        axes_lon = [i for i, d in enumerate(shape) if d == nx]
        if not axes_lat or not axes_lon:
            return None
        axis_lat = axes_lat[0]
        axis_lon = None
        for ax in axes_lon:
            if ax != axis_lat:
                axis_lon = ax
                break
        if axis_lon is None:
            return None
        other_axes = [i for i in range(a.ndim) if i not in (axis_lat, axis_lon)]
        if len(other_axes) != 1:
            return None
        axis_cat = other_axes[0]
        # Reorder to (cat, lat, lon)
        order = [axis_cat, axis_lat, axis_lon]
        aT = np.transpose(a, axes=order)
        if aT.shape[1:] != (ny, nx):
            return None
        return aT  # shape: (k, ny, nx)

    # If requested, build a coverage mask from Daymet grid to clip the global subset strictly to the Daymet domain
    daymet_gmask_sel = None
    if args.clip_to_daymet_domain:
        # Valid Daymet points (where grid exists)
        validD = np.isfinite(lonD) & np.isfinite(latD)
        lonD_ds, latD_ds, validD_ds = downsample(lonD, latD, validD.astype(np.uint8), max_points=args.mask_max_points)
        valid_pts = validD_ds > 0.5
        lon_pts = lonD_ds[valid_pts].ravel()
        lat_pts = latD_ds[valid_pts].ravel()

        if lon_pts.size > 0:
            # Map Daymet points to nearest indices on the global 0.5° rectilinear grid
            def nearest_indices(vals, grid_1d):
                idx = np.searchsorted(grid_1d, vals)
                idx = np.clip(idx, 1, grid_1d.size - 1)
                left = grid_1d[idx - 1]
                right = grid_1d[idx]
                choose_right = (np.abs(vals - right) < np.abs(vals - left))
                out = idx.copy()
                out[~choose_right] = idx[~choose_right] - 1
                return out

            jx = nearest_indices(lon_pts, lonG_1d)
            iy = nearest_indices(lat_pts, latG_1d)
            gmask = np.zeros((latG_1d.size, lonG_1d.size), dtype=bool)
            gmask[iy, jx] = True
            # Apply mask within the selected bbox
            daymet_gmask_sel = gmask[np.ix_(ilat, ilon)]

    # Build list of variables to plot
    var_list = [canonical_var(v) for v in args.vars] if args.vars else [var_name]

    # If plotting multiple variables, ensure output directory exists
    multi = len(var_list) > 1
    if multi:
        args.outdir.mkdir(parents=True, exist_ok=True)

    cmap = make_cmap("viridis")
    for vname in var_list:
        if vname not in dsG.variables:
            print(f"Skipping {vname}: not found in global file.")
            continue
        # Extract and sanitize data for this variable
        arr_raw = dsG[vname].values
        fv = dsG[vname].attrs.get("_FillValue", None)
        mv = dsG[vname].attrs.get("missing_value", None)
        # Try categorical expansion: (k, lat, lon)
        arr3d = expand_to_latlon_stack(arr_raw, latG, lonG)
        if arr3d is not None and arr3d.shape[0] <= 64:
            arr3d = arr3d.astype(np.float64)
            if fv is not None:
                arr3d = np.where(arr3d == fv, np.nan, arr3d)
            if mv is not None:
                arr3d = np.where(arr3d == mv, np.nan, arr3d)
            # Subset and apply masks
            iy_sel = np.where(ilat)[0]
            jx_sel = np.where(ilon)[0]
            k = arr3d.shape[0]
            gstack = arr3d[np.ix_(np.arange(k), iy_sel, jx_sel)]
            if mask_valid_sel is not None:
                gstack = np.where(mask_valid_sel[None, :, :], gstack, np.nan)
            if daymet_gmask_sel is not None:
                gstack = np.where(daymet_gmask_sel[None, :, :], gstack, np.nan)
            # Determine color limits (shared across panels)
            if vname == "LANDFRAC_PFT":
                # Scale fractions to percent and fix 0-100 range
                gstack = gstack * 100.0
                vmin, vmax = 0.0, 100.0
            elif vname == "PCT_URBAN":
                # Percent data; set upper bound to max(20, observed max)
                finite = gstack[np.isfinite(gstack)]
                vmax = float(np.nanmax(finite)) if finite.size > 0 else 20.0
                vmin = 0.0
                vmax = max(20.0, vmax)
            else:
    if args.scale == "robust":
                    data_flat = gstack[np.isfinite(gstack)]
                    if data_flat.size == 0:
                        vmin, vmax = args.map_min, args.map_max
                    else:
                        vmin = float(np.nanpercentile(data_flat, 2))
                        vmax = float(np.nanpercentile(data_flat, 98))
    else:
        vmin = args.map_min
        vmax = args.map_max
                    # Auto-fraction scaling for non-PCT variables if range is [0..~1]
                    if "PCT" not in vname and vmax == 100.0:
                        finite = gstack[np.isfinite(gstack)]
                        if finite.size > 0 and np.nanmax(finite) <= 1.5 and np.nanmin(finite) >= -0.1:
                            vmin, vmax = 0.0, 1.0
            # Layout
            k = arr3d.shape[0]
            ncols = min(5, k)
            nrows = int(np.ceil(k / ncols))
            fig, axes = plt.subplots(nrows, ncols, figsize=(3.2 * ncols, 2.8 * nrows), constrained_layout=True)
            if not isinstance(axes, np.ndarray):
                axes = np.array([[axes]])
            axes = axes.reshape(nrows, ncols)
            title_suffix = "clipped to Daymet domain" if args.clip_to_daymet_domain else "bbox = Daymet region"
            fig.suptitle(f"{vname} — Global 0.5° (original, {title_suffix})", y=0.995)
            # Panel labels: for PCT_NAT_PFT, use PFT0..PFT{k-1}
            panel_labels = None
            if vname == "PCT_NAT_PFT":
                panel_labels = [f"PFT{j}" for j in range(k)]
            for i in range(nrows * ncols):
                r = i // ncols
                c = i % ncols
                ax = axes[r, c]
                ax.set_facecolor("white")
                if i < k:
                    gvar_sel = gstack[i]
                    im = ax.pcolormesh(lon_sel, lat_sel, np.ma.masked_invalid(gvar_sel),
                                       shading="nearest", cmap=cmap, vmin=vmin, vmax=vmax)
                    if panel_labels is not None:
                        ax.set_title(panel_labels[i])
                    else:
                        ax.set_title(f"Band {i+1}")
                else:
                    im = None
                ax.set_xlabel("Lon")
                ax.set_ylabel("Lat")
                try:
                    ax.set_xlim(lon_min, lon_max)
                except Exception:
                    pass
            # Single shared colorbar
            # Pick first valid axis for colorbar anchor
            valid_axes = [axes[r, c] for r in range(nrows) for c in range(ncols) if (r * ncols + c) < k]
            if valid_axes:
                fig.colorbar(im, ax=valid_axes, shrink=0.9)
            out_path = (args.outdir / args.filename_template.format(var=vname)) if multi else args.out
            fig.savefig(out_path, dpi=200)
            plt.close(fig)
            print(f"Wrote {out_path}")
            continue

        # Otherwise, reduce to 2D and plot single panel
        arr2d = reduce_to_latlon_2d(arr_raw, latG, lonG)
        if arr2d is None:
            print(f"Skipping {vname}: cannot align to 2D (lat, lon) grid.")
            continue
        arr2d = arr2d.astype(np.float64)
        if fv is not None:
            arr2d = np.where(arr2d == fv, np.nan, arr2d)
        if mv is not None:
            arr2d = np.where(arr2d == mv, np.nan, arr2d)
        gvar_sel = arr2d[np.ix_(ilat, ilon)]
        if mask_valid_sel is not None:
            gvar_sel = np.where(mask_valid_sel, gvar_sel, np.nan)
        if daymet_gmask_sel is not None:
            gvar_sel = np.where(daymet_gmask_sel, gvar_sel, np.nan)
        if vname == "LANDFRAC_PFT":
            # Scale fractions to percent and fix 0-100 range
            gvar_sel = gvar_sel * 100.0
            vmin, vmax = 0.0, 100.0
        elif vname == "PCT_URBAN":
            # Percent data; set upper bound to max(20, observed max)
            finite = gvar_sel[np.isfinite(gvar_sel)]
            vmax = float(np.nanmax(finite)) if finite.size > 0 else 20.0
            vmin = 0.0
            vmax = max(20.0, vmax)
        else:
            if args.scale == "robust":
                data_flat = gvar_sel[np.isfinite(gvar_sel)]
                if data_flat.size == 0:
                    vmin, vmax = args.map_min, args.map_max
                else:
                    vmin = float(np.nanpercentile(data_flat, 2))
                    vmax = float(np.nanpercentile(data_flat, 98))
            else:
                vmin = args.map_min
                vmax = args.map_max
                if "PCT" not in vname and vmax == 100.0:
                    finite = gvar_sel[np.isfinite(gvar_sel)]
                    if finite.size > 0 and np.nanmax(finite) <= 1.5 and np.nanmin(finite) >= -0.1:
                        vmin, vmax = 0.0, 1.0
        fig, ax = plt.subplots(1, 1, figsize=(9, 6), constrained_layout=True)
        ax.set_facecolor("white")
        title_suffix = "clipped to Daymet domain" if args.clip_to_daymet_domain else "bbox = Daymet region"
        ax.set_title(f"{vname} — Global 0.5° (original, {title_suffix})")
        im0 = ax.pcolormesh(lon_sel, lat_sel, np.ma.masked_invalid(gvar_sel),
                             shading="nearest", cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_xlabel("Longitude (deg)")
        ax.set_ylabel("Latitude (deg)")
        try:
            ax.set_xlim(lon_min, lon_max)
    except Exception:
        pass
        cbar = fig.colorbar(im0, ax=ax, shrink=0.9)
        cbar.set_label(vname)
        out_path = (args.outdir / args.filename_template.format(var=vname)) if multi else args.out
        fig.savefig(out_path, dpi=200)
    plt.close(fig)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()


