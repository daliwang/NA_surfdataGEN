#!/usr/bin/env python3
"""
Generate the 2x2 PFT fraction panel for the Scientific Data paper (Figure 4).

Outputs (by default in ../ relative to this script, i.e. PaperFigures/):
  - pft_1_2_7_8_panel.png

Example:
  python3 generate_pft_panel.py

  python3 generate_pft_panel.py \\
    --surfdata-file /path/to/surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc \\
    --outdir ../
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SURFDATA_FILE = Path(
    "/Users/7xw/Documents/Work/papers/NALCMS_sn-article/"
    "DaymetVeg_LandUnit_DataProduct/"
    "surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.nc"
)
DEFAULT_OUTDIR = SCRIPT_DIR.parent
DEFAULT_OUTPUT_NAME = "pft_1_2_7_8_panel.png"

FONT = {
    "suptitle": 19,
    "title": 17,
    "label": 15,
    "tick": 14,
    "cbar_label": 16,
    "cbar_tick": 15,
}

PFT_PANELS = (
    {
        "code": 1,
        "title": "ELM PFT 1",
        "subtitle": "Needleleaf evergreen temperate",
    },
    {
        "code": 2,
        "title": "ELM PFT 2",
        "subtitle": "Needleleaf evergreen boreal",
    },
    {
        "code": 7,
        "title": "ELM PFT 7",
        "subtitle": "Broadleaf deciduous temperate",
    },
    {
        "code": 8,
        "title": "ELM PFT 8",
        "subtitle": "Broadleaf deciduous boreal",
    },
)


def load_pft_data(
    surfdata_file: Path,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[int]]:
    if not surfdata_file.is_file():
        raise FileNotFoundError(f"Surfdata file not found: {surfdata_file}")

    with xr.open_dataset(surfdata_file) as ds:
        if "PCT_NAT_PFT" not in ds:
            raise KeyError(
                f"Variable 'PCT_NAT_PFT' not found in {surfdata_file}; "
                f"available: {list(ds.data_vars)}"
            )
        pft = ds["PCT_NAT_PFT"].load()
        natveg = ds["PCT_NATVEG"].load() if "PCT_NATVEG" in ds else None
        x = ds["x"].values
        y = ds["y"].values
        natpft = [int(v) for v in ds["natpft"].values]

    return pft.values, x, y, natveg.values if natveg is not None else None, natpft


def extent_from_xy(x: np.ndarray, y: np.ndarray) -> list[float]:
    return [float(np.min(x)), float(np.max(x)), float(np.min(y)), float(np.max(y))]


def mask_ocean(arr: np.ndarray, natveg: np.ndarray | None) -> np.ma.MaskedArray:
    mask = ~np.isfinite(arr)
    if natveg is not None:
        mask |= ~np.isfinite(natveg) | (natveg <= 0)
    return np.ma.array(arr, mask=mask)


def plot_pft_panel(
    pft_data: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    natveg: np.ndarray | None,
    natpft: Sequence[int],
    out_path: Path,
    dpi: int,
) -> None:
    extent = extent_from_xy(x, y)
    fig = plt.figure(figsize=(18.0, 17.0), dpi=dpi)
    gs = fig.add_gridspec(
        2,
        3,
        width_ratios=[1.0, 1.0, 0.05],
        hspace=0.40,
        wspace=0.22,
        left=0.07,
        right=0.91,
        top=0.90,
        bottom=0.06,
    )
    axes = [
        fig.add_subplot(gs[0, 0]),
        fig.add_subplot(gs[0, 1]),
        fig.add_subplot(gs[1, 0]),
        fig.add_subplot(gs[1, 1]),
    ]
    cbar_ax = fig.add_subplot(gs[:, 2])
    fig.suptitle(
        "Distribution of selected ELM PFTs in North America",
        fontsize=FONT["suptitle"],
        y=0.98,
    )

    im = None
    for ax, panel in zip(axes, PFT_PANELS):
        try:
            pft_index = natpft.index(panel["code"])
        except ValueError as exc:
            raise ValueError(
                f"PFT code {panel['code']} not found in natpft dimension: {list(natpft)}"
            ) from exc

        arr = mask_ocean(pft_data[pft_index], natveg)
        # Flip to south-to-north row order so origin="lower" matches MTCO plots.
        arr = arr[::-1, :]
        im = ax.imshow(
            arr,
            origin="lower",
            extent=extent,
            interpolation="nearest",
            aspect="equal",
            cmap="viridis",
            vmin=0,
            vmax=100,
        )
        ax.set_title(
            f"{panel['title']}\n({panel['subtitle']})",
            fontsize=FONT["title"],
            pad=8,
        )
        ax.set_xlabel("X coordinate", fontsize=FONT["label"])
        ax.set_ylabel("Y coordinate", fontsize=FONT["label"])
        ax.tick_params(axis="both", labelsize=FONT["tick"], pad=4)
        ax.set_aspect("equal", adjustable="box")

    if im is not None:
        cbar = fig.colorbar(
            im,
            cax=cbar_ax,
            orientation="vertical",
        )
        cbar.set_label("Percentage", fontsize=FONT["cbar_label"])
        cbar.ax.tick_params(labelsize=FONT["cbar_tick"])

    # Enforce left y-axis after colorbar/layout so right panels match left panels.
    for ax in axes:
        ax.yaxis.tick_left()
        ax.yaxis.set_label_position("left")
        ax.spines["left"].set_visible(True)
        ax.spines["right"].set_visible(True)
        plt.setp(ax.get_yticklabels(), visible=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Saved: {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the 2x2 PFT fraction panel for the paper."
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
        pft_data, x, y, natveg, natpft = load_pft_data(args.surfdata_file)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    out_path = args.outdir.resolve() / args.output_name
    plot_pft_panel(
        pft_data=pft_data,
        x=x,
        y=y,
        natveg=natveg,
        natpft=natpft,
        out_path=out_path,
        dpi=args.dpi,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
