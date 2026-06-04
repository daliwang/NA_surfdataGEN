#!/usr/bin/env python3
"""Sanity checks + full/GL-zoom maps for c260603 surfdata product."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]
NAD = ROOT / "NADaymet"
DOI = NAD / "dataProduct_DOI"
SURF = DOI / "surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260603.nc"
SHP = DOI / "great_lakes_cache/ne_10m_lakes.shp"
OUT_DIR = DOI / "results_c260603_sanity"
FIG_PREFIX = DOI / "figures_c260603"
GL_NAMES = {"Lake Superior", "Lake Michigan", "Lake Huron", "Lake Erie", "Lake Ontario"}
FILL = -32767


def gl_bounds() -> tuple[float, float, float, float]:
    gl = gpd.read_file(SHP)
    if gl.crs is None:
        gl = gl.set_crs("EPSG:4326")
    gl = gl[gl["name"].isin(GL_NAMES)]
    minx, miny, maxx, maxy = gl.total_bounds
    pad = 0.3
    return minx - pad, miny - pad, maxx + pad, maxy + pad


def gl_mask(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    minx, miny, maxx, maxy = gl_bounds()
    return (
        np.isfinite(lon)
        & np.isfinite(lat)
        & (lon >= minx)
        & (lon <= maxx)
        & (lat >= miny)
        & (lat <= maxy)
    )


def plot_full_vs_gl(
    data: np.ndarray,
    lon: np.ndarray,
    lat: np.ndarray,
    title: str,
    out_path: Path,
    cmap: str = "viridis",
    vmin=None,
    vmax=None,
    gl_outline: bool = True,
    cbar_label: str = "%",
) -> None:
    valid = np.isfinite(lon) & np.isfinite(lat)
    d = np.where(valid, data, np.nan)
    gmask = gl_mask(lon, lat)
    rows, cols = np.where(gmask)
    r0, r1 = rows.min(), rows.max() + 1
    c0, c1 = cols.min(), cols.max() + 1

    gl = gpd.read_file(SHP)
    if gl.crs is None:
        gl = gl.set_crs("EPSG:4326")
    gl = gl[gl["name"].isin(GL_NAMES)]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    kw = dict(cmap=cmap, vmin=vmin, vmax=vmax, origin="upper")
    for ax, sub, subt in zip(
        axes,
        [d, d[r0:r1, c0:c1]],
        ["Full domain", "Great Lakes zoom"],
    ):
        im = ax.imshow(sub, **kw)
        if gl_outline and ax is axes[1]:
            gl.boundary.plot(ax=ax, color="cyan", linewidth=0.6, transform=None)
            # overlay in lon/lat: approximate by plotting on same image coords
            # (cells align with lat/lon grid in surfdata)
            sub_lon = lon[r0:r1, c0:c1]
            sub_lat = lat[r0:r1, c0:c1]
            for geom in gl.geometry:
                xs, ys = geom.exterior.xy if geom.geom_type == "Polygon" else geom.xy
                col_idx = []
                row_idx = []
                for x, y in zip(xs, ys):
                    dist = (sub_lon - x) ** 2 + (sub_lat - y) ** 2
                    r, c = np.unravel_index(np.argmin(dist), dist.shape)
                    row_idx.append(r)
                    col_idx.append(c)
                if col_idx:
                    ax.plot(col_idx, row_idx, color="cyan", linewidth=0.5, alpha=0.8)
        ax.set_title(subt)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(title)
    fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.7, label=cbar_label)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out_path.name}")


def extended_sanity(ds: xr.Dataset) -> list[str]:
    lines = []
    lon = ds["LONGXY"].values
    lat = ds["LATIXY"].values
    valid = np.isfinite(lon) & np.isfinite(lat)

    total = ds["total_count"].values.astype(float)
    total[total == FILL] = np.nan
    land = valid & np.isfinite(total) & (total > 0)

    pct_lake = ds["PCT_LAKE"].values.astype(float)
    pct_veg = ds["PCT_NATVEG"].values.astype(float)
    pct_gla = ds["PCT_GLACIER"].values.astype(float)
    pct_urb = ds["PCT_URBAN"].values.astype(float).sum(axis=0)
    lf = ds["land_fraction"].values.astype(float)

    closure = pct_lake + pct_veg + pct_gla + pct_urb
    diff = np.abs(closure[land] - 100.0)
    n_fail = int((diff > 0.01).sum())
    lines.append(f"Land-unit closure failures (>0.01 pp): {n_fail} / {land.sum():,}")
    lines.append(f"  max error: {diff.max():.6f} pp")

    pft = ds["PCT_NAT_PFT"].values.astype(float)
    veg_mask = land & (pct_veg > 0)
    pft_sum = pft[:, veg_mask].sum(axis=0)
    pft_diff = np.abs(pft_sum - 100.0)
    n_pft_fail = int((pft_diff > 0.01).sum())
    lines.append(
        f"PFT closure failures (>0.01 pp): {n_pft_fail} / {veg_mask.sum():,} "
        f"(max {pft_diff.max():.4g} pp)"
    )

    gl = gl_mask(lon, lat) & land
    lines.append(f"GL bbox land cells: {gl.sum():,}")
    lines.append(f"  PCT_LAKE > 0: {(pct_lake[gl] > 0).sum():,}")
    lines.append(f"  PCT_LAKE == 100: {np.isclose(pct_lake[gl], 100).sum():,}")
    lines.append(f"  PCT_LAKE NaN on land: {np.isnan(pct_lake[gl]).sum():,}")

    # open-water fix cells stats (large grid backup not needed on surfdata)
    lines.append(f"land_fraction range on land: {lf[land].min():.2f} – {lf[land].max():.2f}")
    lines.append(f"  partial (<100%): {(lf[land] < 100).sum():,}")

    # problem cell
    j, i = 4746, 5822
    lines.append(
        f"Problem cell (j={j},i={i}): PCT_LAKE={pct_lake[j,i]:.2f}, "
        f"PCT_NATVEG={pct_veg[j,i]:.2f}, land_fraction={lf[j,i]:.2f}, "
        f"total_count={total[j,i]:.0f}"
    )
    return lines


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    val_iv = OUT_DIR / "internal_validation"

    print("========== 1. Great Lakes diagnostic ==========")
    subprocess.run(
        [
            sys.executable,
            str(DOI / "diagnose_great_lakes_pipeline_gap.py"),
            "--surfdata-file",
            str(SURF),
        ],
        check=True,
    )

    print("\n========== 2. Internal validation ==========")
    subprocess.run(
        [
            sys.executable,
            str(DOI / "NALCMS_sn-article/internal_validation/compute_internal_validation.py"),
            "--final-nc",
            str(SURF),
            "--output-dir",
            str(val_iv),
            "--skip-class-count-closure",
        ],
        check=True,
    )

    print("\n========== 3. Extended sanity ==========")
    ds = xr.open_dataset(SURF)
    ext_lines = extended_sanity(ds)

    lon = ds["LONGXY"].values
    lat = ds["LATIXY"].values
    valid = np.isfinite(lon) & np.isfinite(lat)

    lf = ds["land_fraction"].values.astype(float)
    lf[~valid] = np.nan

    pct_lake = ds["PCT_LAKE"].values.astype(float)
    pct_veg = ds["PCT_NATVEG"].values.astype(float)
    pct_gla = ds["PCT_GLACIER"].values.astype(float)
    pct_urb = ds["PCT_URBAN"].values.astype(float).sum(axis=0)
    pft = ds["PCT_NAT_PFT"].values.astype(float)

    for v in [pct_lake, pct_veg, pct_gla, pct_urb, lf]:
        v[~valid] = np.nan

    print("\n".join(ext_lines))

    print("\n========== 4. Figures ==========")
    plot_full_vs_gl(
        lf, lon, lat, "land_fraction (%)", FIG_PREFIX.with_name("figures_c260603_surfdata_land_fraction_full_vs_gl_zoom.png"), cmap="YlGn"
    )
    plot_full_vs_gl(
        pct_veg, lon, lat, "PCT_NATVEG (%)", FIG_PREFIX.with_name("figures_c260603_surfdata_pct_natveg_full_vs_gl_zoom.png")
    )
    plot_full_vs_gl(
        pct_urb, lon, lat, "PCT_URBAN total (%)", FIG_PREFIX.with_name("figures_c260603_surfdata_pct_urban_full_vs_gl_zoom.png"), cmap="Oranges"
    )
    plot_full_vs_gl(
        pct_lake, lon, lat, "PCT_LAKE (%)", FIG_PREFIX.with_name("figures_c260603_surfdata_pct_lake_full_vs_gl_zoom.png"), cmap="Blues"
    )
    plot_full_vs_gl(
        pct_gla, lon, lat, "PCT_GLACIER (%)", FIG_PREFIX.with_name("figures_c260603_surfdata_pct_glacier_full_vs_gl_zoom.png"), cmap="PuBu"
    )

    temp = ds["AvgTempColdMonth"].values.astype(float)
    temp[temp == FILL] = np.nan
    temp[~valid] = np.nan
    land_t = valid & np.isfinite(temp)
    tmin, tmax = float(np.nanmin(temp[land_t])), float(np.nanmax(temp[land_t]))
    plot_full_vs_gl(
        temp,
        lon,
        lat,
        "AvgTempColdMonth (°C) — c260603",
        FIG_PREFIX.with_name("figures_c260603_surfdata_avgtempcoldmonth_full_vs_gl_zoom.png"),
        cmap="RdYlBu_r",
        vmin=tmin,
        vmax=tmax,
        cbar_label="°C",
    )

    for k in range(17):
        arr = pft[k].copy()
        arr[~valid] = np.nan
        plot_full_vs_gl(
            arr,
            lon,
            lat,
            f"PCT_NAT_PFT natpft{k} (%)",
            FIG_PREFIX.with_name(f"figures_c260603_surfdata_pct_natpft{k:02d}_full_vs_gl_zoom.png"),
            cmap="Greens",
            vmax=100,
        )

    ds.close()

    report = OUT_DIR / "SANITY_CHECK_c260603.md"
    iv_sum = val_iv / "internal_validation_summary.md"
    body = [
        "# Sanity Check: surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260603.nc",
        "",
        "**Date:** 2026-06-03 (post open-water recount fix)",
        f"**File:** `{SURF.relative_to(ROOT)}`",
        "",
        "## Extended checks",
        "",
    ]
    body += [f"- {line}" for line in ext_lines]
    body += ["", "## Internal validation", ""]
    if iv_sum.exists():
        body.append(iv_sum.read_text())
    body += [
        "",
        "## Figures",
        "",
        "- `figures_c260603_surfdata_land_fraction_full_vs_gl_zoom.png`",
        "- `figures_c260603_surfdata_pct_natveg_full_vs_gl_zoom.png`",
        "- `figures_c260603_surfdata_pct_urban_full_vs_gl_zoom.png`",
        "- `figures_c260603_surfdata_pct_lake_full_vs_gl_zoom.png`",
        "- `figures_c260603_surfdata_pct_glacier_full_vs_gl_zoom.png`",
        "- `figures_c260603_surfdata_avgtempcoldmonth_full_vs_gl_zoom.png`",
        "- `figures_c260603_surfdata_pct_natpft00` … `natpft16` `_full_vs_gl_zoom.png`",
        "",
        "## Commands",
        "",
        "```bash",
        "python3 run_sanity_and_figures_c260603.py",
        "```",
    ]
    report.write_text("\n".join(body))
    print(f"\nWrote {report}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
