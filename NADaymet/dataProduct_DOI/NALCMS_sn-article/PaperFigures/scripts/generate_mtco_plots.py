#!/usr/bin/env python3
"""
Generate MTCO classification figures for the Scientific Data paper.

Outputs (by default in ../ relative to this script, i.e. PaperFigures/):
  - MTCO_rule1_ranges.png      classified map for Rule 1 (-19, -2 C)
  - MTCO_rule2_ranges.png      classified map for Rule 2 (-15, 5, 18 C)
  - MTCO_rule1_thresholds.png  contour lines at -19 and -2 C
  - MTCO_rule2_thresholds.png  contour lines at -15, 5, and 18 C

Example:
  python3 generate_mtco_plots.py

  python3 generate_mtco_plots.py \\
    --mtco-file /path/to/mean_temperature_coldest_month.nc \\
    --outdir ../ \\
    --plot-type ranges
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MTCO_FILE = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/"
    "NADaymet/dataProduct_DOI/mean_temperature_coldest_month.nc"
)
DEFAULT_OUTDIR = SCRIPT_DIR.parent

FONT = {
    "title": 16,
    "label": 14,
    "tick": 12,
    "legend": 12,
    "legend_title": 12,
    "contour": 12,
}

RULES = {
    "rule1": {
        "thresholds": (-19.0, -2.0),
        "range_colors": ("purple", "green", "yellow"),
        "range_labels": ("<= -19 C", "-19 to -2 C", "> -2 C"),
        "range_title": "MTCO classification for Rule 1 (-19 and -2 C)",
        "threshold_title": "MTCO Rule 1 thresholds (-19 and -2 C)",
    },
    "rule2": {
        "thresholds": (-15.0, 5.0, 18.0),
        "range_colors": ("#1f77b4", "#ff9900", "yellow", "red"),
        "range_labels": ("<= -15 C", "-15 to 5 C", "5 to 18 C", "> 18 C"),
        "range_title": "MTCO classification for Rule 2 (-15, 5, and 18 C)",
        "threshold_title": "MTCO Rule 2 thresholds (-15, 5, and 18 C)",
    },
}


def load_mtco(mtco_file: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not mtco_file.is_file():
        raise FileNotFoundError(f"MTCO file not found: {mtco_file}")

    with xr.open_dataset(mtco_file) as ds:
        if "AvgTemp" not in ds:
            raise KeyError(
                f"Variable 'AvgTemp' not found in {mtco_file}; "
                f"available: {list(ds.data_vars)}"
            )
        da = ds["AvgTemp"].load()

    arr = da.values.astype(float)
    x = da.coords["x"].values if "x" in da.coords else np.arange(arr.shape[1])
    y = da.coords["y"].values if "y" in da.coords else np.arange(arr.shape[0])
    return arr, x, y


def classify_ranges(
    arr: np.ndarray, thresholds: Sequence[float]
) -> np.ma.MaskedArray:
    mask = ~np.isfinite(arr)
    cls = np.full(arr.shape, np.nan, dtype=float)
    sorted_thresh = sorted(float(t) for t in thresholds)
    for idx, threshold in enumerate(sorted_thresh):
        if idx == 0:
            cls[(arr <= threshold) & ~mask] = 0
        else:
            lower = sorted_thresh[idx - 1]
            cls[(arr > lower) & (arr <= threshold) & ~mask] = idx
    cls[(arr > sorted_thresh[-1]) & ~mask] = len(sorted_thresh)
    return np.ma.masked_invalid(cls)


def plot_classified_ranges(
    arr: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    thresholds: Sequence[float],
    colors: Sequence[str],
    labels: Sequence[str],
    title: str,
    out_path: Path,
    dpi: int,
) -> None:
    n_classes = len(thresholds) + 1
    if len(colors) != n_classes or len(labels) != n_classes:
        raise ValueError(
            f"Expected {n_classes} colors and labels for thresholds {thresholds}, "
            f"got {len(colors)} colors and {len(labels)} labels"
        )

    classified = classify_ranges(arr, thresholds)
    extent = [float(np.min(x)), float(np.max(x)), float(np.min(y)), float(np.max(y))]

    cmap = ListedColormap(colors)
    cmap.set_bad("white")
    norm = BoundaryNorm(np.arange(-0.5, n_classes + 0.5, 1.0), cmap.N)

    fig, ax = plt.subplots(figsize=(8.8, 6.8), dpi=dpi)
    ax.imshow(
        classified,
        cmap=cmap,
        norm=norm,
        origin="lower",
        extent=extent,
        interpolation="nearest",
    )
    ax.set_title(title, fontsize=FONT["title"])
    ax.set_xlabel("X coordinate", fontsize=FONT["label"])
    ax.set_ylabel("Y coordinate", fontsize=FONT["label"])
    ax.tick_params(axis="both", labelsize=FONT["tick"])
    handles = [
        Patch(facecolor=c, edgecolor="black", linewidth=0.3, label=label)
        for c, label in zip(colors, labels)
    ]
    ax.legend(
        handles=handles,
        title="MTCO range",
        loc="lower left",
        fontsize=FONT["legend"],
        title_fontsize=FONT["legend_title"],
        frameon=True,
    )
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_threshold_contours(
    arr: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    thresholds: Sequence[float],
    title: str,
    out_path: Path,
    dpi: int,
) -> None:
    mask = ~np.isfinite(arr)
    masked = np.ma.array(arr, mask=mask)

    fig, ax = plt.subplots(figsize=(8.5, 6.5), dpi=dpi)
    levels = list(thresholds)
    cs = ax.contour(x, y, masked, levels=levels, colors="k", linewidths=0.8)
    ax.clabel(cs, inline=True, fontsize=FONT["contour"], fmt="%g C")
    ax.set_title(
        f"{title} (levels {', '.join(str(v) for v in levels)} C)",
        fontsize=FONT["title"],
    )
    ax.set_xlabel("Longitude", fontsize=FONT["label"])
    ax.set_ylabel("Latitude", fontsize=FONT["label"])
    ax.tick_params(axis="both", labelsize=FONT["tick"])
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Saved: {out_path}")


def parse_plot_types(raw: Iterable[str]) -> set[str]:
    allowed = {"ranges", "thresholds", "all"}
    selected = {v.lower() for v in raw}
    unknown = selected - allowed
    if unknown:
        raise ValueError(f"Unknown plot type(s): {sorted(unknown)}; choose from {sorted(allowed)}")
    if "all" in selected:
        return {"ranges", "thresholds"}
    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate MTCO Rule 1 and Rule 2 figures for the paper."
    )
    parser.add_argument(
        "--mtco-file",
        type=Path,
        default=DEFAULT_MTCO_FILE,
        help="Path to mean_temperature_coldest_month.nc (variable AvgTemp)",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=DEFAULT_OUTDIR,
        help="Directory for output PNG files (default: PaperFigures/)",
    )
    parser.add_argument(
        "--plot-type",
        nargs="+",
        default=["all"],
        choices=["ranges", "thresholds", "all"],
        help="Which figure types to generate",
    )
    parser.add_argument("--dpi", type=int, default=220, help="Figure DPI")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plot_types = parse_plot_types(args.plot_type)

    try:
        arr, x, y = load_mtco(args.mtco_file)
    except (FileNotFoundError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    outdir = args.outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    for rule_name, cfg in RULES.items():
        thresholds = cfg["thresholds"]
        if "ranges" in plot_types:
            plot_classified_ranges(
                arr=arr,
                x=x,
                y=y,
                thresholds=thresholds,
                colors=cfg["range_colors"],
                labels=cfg["range_labels"],
                title=cfg["range_title"],
                out_path=outdir / f"MTCO_{rule_name}_ranges.png",
                dpi=args.dpi,
            )
        if "thresholds" in plot_types:
            plot_threshold_contours(
                arr=arr,
                x=x,
                y=y,
                thresholds=thresholds,
                title=cfg["threshold_title"],
                out_path=outdir / f"MTCO_{rule_name}_thresholds.png",
                dpi=args.dpi,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
