#!/usr/bin/env python3
"""
Generate 3-panel Li et al. (2020) vs NALCMS comparison figures for the paper.

Each output figure has one row: NALCMS | Li et al. 2020 LULC | NALCMS - Li et al.

Outputs (default under PaperFigures/comparison/li_lulc_2020/):
  - pct_lake_lulc2020_vs_nalcms_panel.png
  - pct_natveg_lulc2020_vs_nalcms_panel.png
  - pct_glacier_lulc2020_vs_nalcms_panel.png
  - pct_urban_lulc2020_vs_nalcms_panel.png

Example:
  python3 generate_li_lulc_comparison.py

  python3 generate_li_lulc_comparison.py \\
    --lulc-dir /path/to/references/LULC \\
    --nalcms-file /path/to/surfdata...great_lakes_fix.nc
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
COMPARE_SCRIPT = (
    REPO_ROOT
    / "DaymetVeg_LandUnit_DataProduct"
    / "comparison"
    / "compare_lulc_vs_nalcms_2020_vars.py"
)
DEFAULT_NALCMS = (
    REPO_ROOT
    / "DaymetVeg_LandUnit_DataProduct"
    / "surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc"
)
DEFAULT_LULC_DIR = REPO_ROOT / "DaymetVeg_LandUnit_DataProduct" / "references" / "LULC"
DEFAULT_OUTDIR = SCRIPT_DIR.parent / "comparison" / "li_lulc_2020"
DEFAULT_VARS = ["PCT_LAKE", "PCT_NATVEG", "PCT_GLACIER", "PCT_URBAN"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Paper wrapper: Li et al. 2020 LULC vs NALCMS 3-panel comparison figures."
    )
    parser.add_argument("--lulc-dir", type=Path, default=DEFAULT_LULC_DIR)
    parser.add_argument("--nalcms-file", type=Path, default=DEFAULT_NALCMS)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument(
        "--vars",
        nargs="+",
        default=DEFAULT_VARS,
        help="Land-unit variables to compare (default: lake, natveg, glacier, urban).",
    )
    parser.add_argument("--urban-mode", choices=["stream", "load"], default="stream")
    parser.add_argument("--scale", choices=["robust", "fixed"], default="fixed")
    parser.add_argument("--map-min", type=float, default=0.0)
    parser.add_argument("--map-max", type=float, default=100.0)
    parser.add_argument("--diff-lim", type=float, default=100.0)
    args = parser.parse_args()

    if not COMPARE_SCRIPT.is_file():
        print(f"Comparison script not found: {COMPARE_SCRIPT}", file=sys.stderr)
        return 1
    if not args.nalcms_file.is_file():
        print(f"NALCMS surfdata file not found: {args.nalcms_file}", file=sys.stderr)
        return 1
    if not args.lulc_dir.is_dir():
        print(f"LULC reference directory not found: {args.lulc_dir}", file=sys.stderr)
        print("Download Li et al. 2020 LULC NetCDF files (see references/LULC/Readme.txt).", file=sys.stderr)
        return 1

    args.outdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(COMPARE_SCRIPT),
        "--lulc-dir",
        str(args.lulc_dir),
        "--nalcms-file",
        str(args.nalcms_file),
        "--outdir",
        str(args.outdir),
        "--layout",
        "triple",
        "--paper-style",
        "--vars",
        *args.vars,
        "--urban-mode",
        args.urban_mode,
        "--scale",
        args.scale,
        "--map-min",
        str(args.map_min),
        "--map-max",
        str(args.map_max),
        "--diff-lim",
        str(args.diff_lim),
    ]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
