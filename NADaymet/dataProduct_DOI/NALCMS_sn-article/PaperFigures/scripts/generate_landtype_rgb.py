#!/usr/bin/env python3
"""
Generate the integrated land-unit RGB map for the Scientific Data paper (Figure 5).

Outputs (by default in ../ relative to this script, i.e. PaperFigures/):
  - landtype_rgb_map.png

RGB channels (0--100% scaled to 0--1):
  - Red: total urban (sum of PCT_URBAN)
  - Green: natural vegetation (PCT_NATVEG)
  - Blue: lake/water (PCT_LAKE)

Glacier is not a fourth RGB channel. Each cell is alpha-blended toward dark gray
by PCT_GLACIER so ice is distinguishable from the white ocean background.
The legend shows vegetation, urban, lake, and glacier only.

Example:
  python3 generate_landtype_rgb.py

  python3 generate_landtype_rgb.py \\
    --surfdata-file /path/to/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc \\
    --outdir ../
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.patches import Patch

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SURFDATA_FILE = Path(
    "/Users/7xw/Documents/Work/papers/NALCMS_sn-article/"
    "DaymetVeg_LandUnit_DataProduct/"
    "surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc"
)
DEFAULT_OUTDIR = SCRIPT_DIR.parent
DEFAULT_OUTPUT_NAME = "landtype_rgb_map.png"

# Dark gray for glacier; distinct from white ocean background.
GLACIER_COLOR = np.array([0.38, 0.38, 0.40])

FONT = {
    "title": 17,
    "label": 15,
    "tick": 14,
    "legend": 13,
}


def load_landtype_fields(surfdata_file: Path) -> Tuple[np.ndarray, ...]:
    if not surfdata_file.is_file():
        raise FileNotFoundError(f"Surfdata file not found: {surfdata_file}")

    with xr.open_dataset(surfdata_file) as ds:
        required = ("PCT_NATVEG", "PCT_LAKE", "PCT_GLACIER", "PCT_URBAN")
        missing = [name for name in required if name not in ds]
        if missing:
            raise KeyError(
                f"Missing variable(s) {missing} in {surfdata_file}; "
                f"available: {list(ds.data_vars)}"
            )

        veg = ds["PCT_NATVEG"].load().values.astype(float)
        lake = ds["PCT_LAKE"].load().values.astype(float)
        glacier = ds["PCT_GLACIER"].load().values.astype(float)
        urban = ds["PCT_URBAN"].load().sum("numurbl").values.astype(float)
        x = ds["x"].values
        y = ds["y"].values

    return veg, lake, glacier, urban, x, y


def extent_from_xy(x: np.ndarray, y: np.ndarray) -> list[float]:
    return [float(np.min(x)), float(np.max(x)), float(np.min(y)), float(np.max(y))]


def build_rgb_array(
    veg: np.ndarray,
    lake: np.ndarray,
    urban: np.ndarray,
    glacier: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    veg = np.where(np.isfinite(veg), veg, 0.0)
    lake = np.where(np.isfinite(lake), lake, 0.0)
    urban = np.where(np.isfinite(urban), urban, 0.0)
    glacier = np.where(np.isfinite(glacier), glacier, 0.0)

    valid = (
        np.isfinite(veg)
        & np.isfinite(lake)
        & np.isfinite(urban)
        & np.isfinite(glacier)
    )
    land_present = valid & ((veg + lake + urban + glacier) > 0)

    red = np.clip(urban, 0.0, 100.0) / 100.0
    green = np.clip(veg, 0.0, 100.0) / 100.0
    blue = np.clip(lake, 0.0, 100.0) / 100.0

    rgb = np.stack([red, green, blue], axis=-1)
    rgb = np.clip(rgb, 0.0, 1.0)

    # Blend toward glacier gray by PCT_GLACIER (fourth land unit, not an RGB channel).
    gl_frac = np.clip(glacier, 0.0, 100.0) / 100.0
    rgb = rgb * (1.0 - gl_frac[..., np.newaxis]) + GLACIER_COLOR * gl_frac[..., np.newaxis]

    rgb[~land_present] = 1.0  # white background for ocean / no-data cells
    return rgb, land_present


def add_landtype_legend(ax: plt.Axes) -> None:
    handles = [
        Patch(facecolor=(0.0, 0.85, 0.0), edgecolor="0.3", linewidth=0.5, label="Vegetation"),
        Patch(facecolor=(0.90, 0.0, 0.0), edgecolor="0.3", linewidth=0.5, label="Urban"),
        Patch(facecolor=(0.0, 0.40, 0.90), edgecolor="0.3", linewidth=0.5, label="Lake"),
        Patch(facecolor=GLACIER_COLOR, edgecolor="0.3", linewidth=0.5, label="Glacier"),
    ]
    ax.legend(
        handles=handles,
        loc="lower left",
        bbox_to_anchor=(0.02, 0.02),
        bbox_transform=ax.transAxes,
        borderaxespad=0.0,
        fontsize=FONT["legend"],
        framealpha=0.92,
        edgecolor="0.6",
    )


def plot_landtype_rgb(
    veg: np.ndarray,
    lake: np.ndarray,
    glacier: np.ndarray,
    urban: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    out_path: Path,
    dpi: int,
) -> None:
    extent = extent_from_xy(x, y)
    rgb, _land_present = build_rgb_array(veg, lake, urban, glacier)

    # Match MTCO/PFT maps: south-to-north row order with origin="lower".
    rgb = rgb[::-1, :, :]

    fig, ax = plt.subplots(figsize=(10.5, 8.5), dpi=dpi)
    ax.imshow(
        rgb,
        origin="lower",
        extent=extent,
        interpolation="nearest",
        aspect="equal",
    )

    ax.set_title(
        "Combined map for land types (1-km grid)",
        fontsize=FONT["title"],
        pad=10,
    )
    ax.set_xlabel("X coordinate", fontsize=FONT["label"])
    ax.set_ylabel("Y coordinate", fontsize=FONT["label"])
    ax.tick_params(axis="both", labelsize=FONT["tick"], pad=4)
    ax.set_aspect("equal", adjustable="box")

    fig.tight_layout()
    add_landtype_legend(ax)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Saved: {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the integrated land-unit RGB map for the paper."
    )
    parser.add_argument(
        "--surfdata-file",
        type=Path,
        default=DEFAULT_SURFDATA_FILE,
        help="Path to surfdata NetCDF (c260128 or compatible)",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=DEFAULT_OUTDIR,
        help="Output directory (default: PaperFigures/)",
    )
    parser.add_argument(
        "--output-name",
        default=DEFAULT_OUTPUT_NAME,
        help="Output PNG filename",
    )
    parser.add_argument("--dpi", type=int, default=180, help="Figure DPI")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        veg, lake, glacier, urban, x, y = load_landtype_fields(args.surfdata_file)
    except (FileNotFoundError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    out_path = args.outdir.resolve() / args.output_name
    plot_landtype_rgb(
        veg=veg,
        lake=lake,
        glacier=glacier,
        urban=urban,
        x=x,
        y=y,
        out_path=out_path,
        dpi=args.dpi,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
