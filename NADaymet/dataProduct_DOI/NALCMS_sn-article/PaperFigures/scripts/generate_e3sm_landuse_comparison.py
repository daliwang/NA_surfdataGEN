#!/usr/bin/env python3
"""
Generate 3-panel E3SM historical land-use (2015) vs NALCMS comparison figures.

Each output figure has one row: NALCMS | E3SM 2015 | NALCMS - E3SM 2015

Outputs (default under PaperFigures/comparison/e3sm_landuse_2015/):
  - pct_lake_e3sm2015_vs_nalcms_panel.png
  - pct_natveg_e3sm2015_vs_nalcms_panel.png
  - pct_glacier_e3sm2015_vs_nalcms_panel.png
  - pct_urban_e3sm2015_vs_nalcms_panel.png
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
    / "compare_e3sm_landuse_vs_nalcms.py"
)
DEFAULT_E3SM = (
    REPO_ROOT
    / "DaymetVeg_LandUnit_DataProduct"
    / "comparison"
    / "landuse.PCT_subset_last.nc"
)
DEFAULT_NALCMS = (
    REPO_ROOT
    / "DaymetVeg_LandUnit_DataProduct"
    / "surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc"
)
DEFAULT_OUTDIR = SCRIPT_DIR.parent / "comparison" / "e3sm_landuse_2015"
DEFAULT_VARS = ["PCT_LAKE", "PCT_NATVEG", "PCT_GLACIER", "PCT_URBAN"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Paper wrapper: E3SM 2015 land-use vs NALCMS 3-panel comparison figures."
    )
    parser.add_argument("--e3sm-file", type=Path, default=DEFAULT_E3SM)
    parser.add_argument("--nalcms-file", type=Path, default=DEFAULT_NALCMS)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--vars", nargs="+", default=DEFAULT_VARS)
    parser.add_argument("--scale", choices=["robust", "fixed"], default="fixed")
    parser.add_argument("--map-min", type=float, default=0.0)
    parser.add_argument("--map-max", type=float, default=100.0)
    parser.add_argument("--diff-lim", type=float, default=100.0)
    args = parser.parse_args()

    if not COMPARE_SCRIPT.is_file():
        print(f"Comparison script not found: {COMPARE_SCRIPT}", file=sys.stderr)
        return 1
    if not args.e3sm_file.is_file():
        print(f"E3SM land-use file not found: {args.e3sm_file}", file=sys.stderr)
        return 1
    if not args.nalcms_file.is_file():
        print(f"NALCMS surfdata file not found: {args.nalcms_file}", file=sys.stderr)
        return 1

    args.outdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(COMPARE_SCRIPT),
        "--e3sm-file",
        str(args.e3sm_file),
        "--nalcms-file",
        str(args.nalcms_file),
        "--outdir",
        str(args.outdir),
        "--vars",
        *args.vars,
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
    return subprocess.call(cmd, cwd=str(COMPARE_SCRIPT.parent))


if __name__ == "__main__":
    raise SystemExit(main())
