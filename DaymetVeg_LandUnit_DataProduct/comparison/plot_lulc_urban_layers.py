import argparse
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt


def make_cmap(name: str):
    cmap = plt.get_cmap(name).copy()
    cmap.set_bad(color=(0.0, 0.0, 0.0, 0.0))
    return cmap


def prepare_imshow(z, lon, lat):
    xg = lon
    yg = lat
    z_plot = z
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


def compute_stride(ny: int, nx: int, max_points: int = 1_000_000) -> int:
    if nx * ny > max_points:
        return max(1, int(np.ceil(np.sqrt((nx * ny) / max_points))))
    return 1


def main():
    ap = argparse.ArgumentParser(description="Plot 3 native layers of LULC PCT_URBAN for sanity check (no regrid).")
    ap.add_argument("--lulc-file", type=Path, required=False,
                    default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/references/LULC/PCT_URBAN_2020_1k_c230606.nc"))
    ap.add_argument("--out", type=Path, required=False,
                    default=Path("/gpfs/wolf2/cades/cli185/proj-shared/wangd/kiloCraft/NA_surfdataGEN/DaymetVeg_LandUnit_DataProduct/comparison/lulc_2020_compare/pct_urban_layers_native.png"))
    ap.add_argument("--max-points", type=int, default=1_000_000, help="Target max pixels per layer for plotting.")
    args = ap.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    ds = xr.open_dataset(args.lulc_file)
    if "PCT_URBAN" not in ds.data_vars:
        raise SystemExit("PCT_URBAN not found in LULC file.")

    # Identify dims
    urban = ds["PCT_URBAN"]
    # Detect fill/missing values
    fv = urban.attrs.get("_FillValue", None)
    mv = urban.attrs.get("missing_value", None)
    # Find category dim
    cat_dim = None
    for d in urban.dims:
        if d in {"density_class", "numurbl", "urban_class", "urbl"}:
            cat_dim = d
            break
    if cat_dim is None:
        # Fall back: assume first axis
        cat_dim = urban.dims[0]

    # Get 1D lat/lon and form meshgrid just for extent/orientation
    lat = ds["lat"].values
    lon = ds["lon"].values
    ny, nx = lat.size, lon.size
    stride = compute_stride(ny, nx, args.max_points)
    lat_s = lat[::stride]
    lon_s = lon[::stride]
    lon2d, lat2d = np.meshgrid(lon_s, lat_s, indexing="xy")

    # Prepare figure
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
    cmap = make_cmap("viridis")
    vmin, vmax = 0.0, 100.0
    last_im = None
    for i in range(3):
        ax = axes[i]
        ax.set_facecolor("white")
        # Slice layer i if exists; otherwise plot zeros to keep layout consistent
        layer = urban.isel({cat_dim: i}) if i < urban.sizes.get(cat_dim, 0) else None
        if layer is not None:
            # Stride read to avoid loading full array
            z = layer.astype(np.float32).values[::stride, ::stride]
            # Apply fill/missing masks explicitly
            if fv is not None:
                try:
                    z = np.where(z == float(fv), np.nan, z)
                except Exception:
                    pass
            if mv is not None:
                try:
                    z = np.where(z == float(mv), np.nan, z)
                except Exception:
                    pass
        else:
            z = np.zeros_like(lon2d, dtype=np.float32)
        z_plot, extent, origin = prepare_imshow(z, lon2d, lat2d)
        im = ax.imshow(np.ma.masked_invalid(z_plot), origin=origin, extent=extent,
                       cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
        last_im = im
        ax.set_title(f"PCT_URBAN layer {i}")
        ax.set_xlabel("Longitude (deg)")
        ax.set_ylabel("Latitude (deg)")
    if last_im is not None:
        cbar = fig.colorbar(last_im, ax=axes.ravel().tolist(), shrink=0.9)
        cbar.set_label("PCT_URBAN (%)")
    fig.savefig(args.out, dpi=180)
    plt.close(fig)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()

