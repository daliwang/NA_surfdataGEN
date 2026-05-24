#!/usr/bin/env python3
"""Compute internal validation metrics for the NALCMS-to-Daymet ELM product.

The script reads generated intermediate files from the NALCMS/Daymet workflow and
produces CSV/Markdown summaries that can be used in the manuscript Technical
Validation section.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import rasterio
from netCDF4 import Dataset


DEFAULT_DATA_ROOT = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet"
)
DEFAULT_FINAL_NC = Path(
    "/Users/7xw/Documents/Work/papers/NALCMS_sn-article/"
    "DaymetVeg_LandUnit_DataProduct/"
    "surfdata.Daymet_NA.nalcms.1km.2d.VegMapLandUnitTemp.c260128.great_lakes_fix.nc"
)


@dataclass
class Metric:
    category: str
    check: str
    value: str
    units: str = ""
    notes: str = ""


def as_array(values) -> np.ndarray:
    """Return a plain ndarray with masked values represented as NaN."""
    arr = np.asanyarray(values)
    if np.ma.isMaskedArray(arr):
        if np.issubdtype(arr.dtype, np.floating):
            arr = arr.filled(np.nan)
        else:
            arr = arr.filled(-9999)
    return np.asarray(arr)


def finite_stats(values: np.ndarray) -> dict[str, float]:
    vals = np.asarray(values)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return {"min": math.nan, "max": math.nan, "mean": math.nan}
    return {
        "min": float(np.min(vals)),
        "max": float(np.max(vals)),
        "mean": float(np.mean(vals)),
    }


def fmt(value: float | int) -> str:
    if isinstance(value, (np.integer, int)):
        return str(int(value))
    if isinstance(value, (np.floating, float)):
        if math.isnan(float(value)):
            return "NA"
        return f"{float(value):.6g}"
    return str(value)


def write_metrics(path: Path, rows: list[Metric]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "check", "value", "units", "notes"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def write_table(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def rows(height: int, block_size: int) -> Iterable[tuple[int, int]]:
    for start in range(0, height, block_size):
        yield start, min(start + block_size, height)


def nc_var(ds: Dataset, name: str, start: int, stop: int) -> np.ndarray:
    var = ds.variables[name]
    if len(var.dimensions) == 2:
        return as_array(var[start:stop, :])
    if len(var.dimensions) == 3:
        return as_array(var[:, start:stop, :])
    raise ValueError(f"Unsupported variable rank for {name}: {var.dimensions}")


def compute_final_product_checks(final_nc: Path, block_size: int, tol: float) -> list[Metric]:
    metrics: list[Metric] = []
    with Dataset(final_nc) as ds:
        height = len(ds.dimensions["y"])
        pft_errors = []
        landunit_errors = []
        total_land_cells = 0
        pft_valid_cells = 0
        pft_failures = 0
        landunit_valid_cells = 0
        landunit_failures = 0
        full_land_cells = 0
        partial_land_cells = 0
        for start, stop in rows(height, block_size):
            pct_nat_pft = nc_var(ds, "PCT_NAT_PFT", start, stop)
            total_count = nc_var(ds, "total_count", start, stop)
            pct_natveg = nc_var(ds, "PCT_NATVEG", start, stop)
            pct_lake = nc_var(ds, "PCT_LAKE", start, stop)
            pct_glacier = nc_var(ds, "PCT_GLACIER", start, stop)
            pct_urban = nc_var(ds, "PCT_URBAN", start, stop)

            land_mask = np.isfinite(total_count) & (total_count > 0)
            total_land_cells += int(np.sum(land_mask))
            full_land_cells += int(np.sum(land_mask & (total_count >= 1089)))
            partial_land_cells += int(np.sum(land_mask & (total_count < 1089)))

            pft_sum = np.nansum(pct_nat_pft, axis=0)
            pft_mask = land_mask & np.isfinite(pct_natveg) & (pct_natveg > 0) & np.isfinite(pft_sum)
            if np.any(pft_mask):
                err = np.abs(pft_sum[pft_mask] - 100.0)
                pft_errors.append(err)
                pft_valid_cells += int(err.size)
                pft_failures += int(np.sum(err > tol))

            urban_sum = np.nansum(pct_urban, axis=0)
            landunit_sum = pct_natveg + pct_lake + pct_glacier + urban_sum
            lu_mask = land_mask & np.isfinite(landunit_sum)
            if np.any(lu_mask):
                err = np.abs(landunit_sum[lu_mask] - 100.0)
                landunit_errors.append(err)
                landunit_valid_cells += int(err.size)
                landunit_failures += int(np.sum(err > tol))

        pft_err = np.concatenate(pft_errors) if pft_errors else np.array([])
        landunit_err = np.concatenate(landunit_errors) if landunit_errors else np.array([])

        metrics.extend(
            [
                Metric("final product", "source file", final_nc.name, "", str(final_nc)),
                Metric("final product", "valid land cells", fmt(total_land_cells), "cells"),
                Metric("final product", "full-land cells", fmt(full_land_cells), "cells", "total_count >= 1089"),
                Metric("final product", "partial-land cells", fmt(partial_land_cells), "cells", "0 < total_count < 1089"),
                Metric("final product", "PFT closure cells checked", fmt(pft_valid_cells), "cells"),
                Metric("final product", "PFT closure failures", fmt(pft_failures), "cells", f"absolute error > {tol}"),
                Metric(
                    "final product",
                    "maximum PFT closure error",
                    fmt(float(np.max(pft_err)) if pft_err.size else math.nan),
                    "percentage points",
                ),
                Metric(
                    "final product",
                    "mean PFT closure error",
                    fmt(float(np.mean(pft_err)) if pft_err.size else math.nan),
                    "percentage points",
                ),
                Metric("final product", "land-unit closure cells checked", fmt(landunit_valid_cells), "cells"),
                Metric("final product", "land-unit closure failures", fmt(landunit_failures), "cells", f"absolute error > {tol}"),
                Metric(
                    "final product",
                    "maximum land-unit closure error",
                    fmt(float(np.max(landunit_err)) if landunit_err.size else math.nan),
                    "percentage points",
                ),
                Metric(
                    "final product",
                    "mean land-unit closure error",
                    fmt(float(np.mean(landunit_err)) if landunit_err.size else math.nan),
                    "percentage points",
                ),
            ]
        )
    return metrics


def compute_intermediate_count_closure(
    landunit_nc: Path, class_count_dir: Path, block_size: int
) -> list[Metric]:
    class_paths = [class_count_dir / f"landtype{i}_count_in_namask.tif" for i in range(1, 20)]
    missing = [str(path) for path in class_paths if not path.exists()]
    metrics: list[Metric] = []
    if missing:
        return [
            Metric(
                "intermediate counts",
                "class-count closure skipped",
                "missing files",
                notes="; ".join(missing),
            )
        ]

    with Dataset(landunit_nc) as ds, rasterio.open(class_paths[0]) as src0:
        total_var = ds.variables["total_count"]
        height = total_var.shape[-2]
        width = total_var.shape[-1]
        if src0.height != height or src0.width != width:
            metrics.append(
                Metric(
                    "intermediate counts",
                    "class-count closure skipped",
                    "shape mismatch",
                    notes=f"NetCDF {(height, width)} vs raster {(src0.height, src0.width)}",
                )
            )
            return metrics

        failures = 0
        checked = 0
        max_abs_residual = 0
        residual_sum = 0
        full_land_cells = 0
        partial_land_cells = 0
        valid_land_cells = 0
        landunit_errors = []
        landunit_valid_cells = 0
        landunit_failures = 0
        land_fraction_values = []
        for start, stop in rows(height, block_size):
            total = as_array(total_var[0, start:stop, :]).astype(np.int64)
            count_sum = np.zeros_like(total, dtype=np.int64)
            window = rasterio.windows.Window(0, start, width, stop - start)
            for path in class_paths:
                with rasterio.open(path) as src:
                    arr = src.read(1, window=window).astype(np.int64)
                arr = np.where(arr < 0, 0, arr)
                count_sum += arr
            valid = total >= 0
            residual = count_sum[valid] - total[valid]
            if residual.size:
                abs_residual = np.abs(residual)
                failures += int(np.sum(abs_residual != 0))
                checked += int(abs_residual.size)
                max_abs_residual = max(max_abs_residual, int(np.max(abs_residual)))
                residual_sum += int(np.sum(abs_residual))

            land_mask = total > 0
            valid_land_cells += int(np.sum(land_mask))
            full_land_cells += int(np.sum(land_mask & (total >= 1089)))
            partial_land_cells += int(np.sum(land_mask & (total < 1089)))

            pft_pct = as_array(ds.variables["pft_percentage"][0, start:stop, :])
            urban_pct = as_array(ds.variables["urban_percentage"][0, start:stop, :])
            lake_pct = as_array(ds.variables["lake_percentage"][0, start:stop, :])
            glacier_pct = as_array(ds.variables["glacier_percentage"][0, start:stop, :])
            land_fraction = as_array(ds.variables["land_fraction"][0, start:stop, :])
            landunit_sum = pft_pct + urban_pct + lake_pct + glacier_pct
            lu_mask = land_mask & np.isfinite(landunit_sum)
            if np.any(lu_mask):
                err = np.abs(landunit_sum[lu_mask] - 100.0)
                landunit_errors.append(err)
                landunit_valid_cells += int(err.size)
                landunit_failures += int(np.sum(err > 1e-3))
            if np.any(land_mask):
                lf = land_fraction[land_mask]
                land_fraction_values.append(lf[np.isfinite(lf)])

    landunit_err = np.concatenate(landunit_errors) if landunit_errors else np.array([])
    lf_all = np.concatenate(land_fraction_values) if land_fraction_values else np.array([])
    metrics.extend(
        [
            Metric("intermediate land units", "valid land cells", fmt(valid_land_cells), "cells"),
            Metric("intermediate land units", "full-land cells", fmt(full_land_cells), "cells", "total_count >= 1089"),
            Metric("intermediate land units", "partial-land cells", fmt(partial_land_cells), "cells", "0 < total_count < 1089"),
            Metric("intermediate land units", "land-unit closure cells checked", fmt(landunit_valid_cells), "cells"),
            Metric("intermediate land units", "land-unit closure failures", fmt(landunit_failures), "cells", "absolute error > 0.001"),
            Metric(
                "intermediate land units",
                "maximum land-unit closure error",
                fmt(float(np.max(landunit_err)) if landunit_err.size else math.nan),
                "percentage points",
            ),
            Metric(
                "intermediate land units",
                "mean land-unit closure error",
                fmt(float(np.mean(landunit_err)) if landunit_err.size else math.nan),
                "percentage points",
            ),
            Metric("intermediate counts", "class-count closure cells checked", fmt(checked), "cells"),
            Metric("intermediate counts", "class-count closure failures", fmt(failures), "cells"),
            Metric("intermediate counts", "maximum class-count residual", fmt(max_abs_residual), "30 m pixels"),
            Metric("intermediate counts", "sum absolute class-count residual", fmt(residual_sum), "30 m pixels"),
        ]
    )
    for stat_name, stat_value in finite_stats(lf_all).items():
        metrics.append(Metric("intermediate land units", f"land_fraction {stat_name}", fmt(stat_value), "percent"))
    return metrics


def parse_landtype_id(name: str) -> int | None:
    match = re.search(r"landtype(\d+)", name)
    return int(match.group(1)) if match else None


def parse_bounds(bounds: str) -> tuple[float, float] | None:
    le_match = re.search(r"<=\s*([-+]?\d+(?:\.\d+)?)", bounds)
    gt_match = re.search(r">\s*([-+]?\d+(?:\.\d+)?)", bounds)
    if not le_match or not gt_match:
        return None
    return float(le_match.group(1)), float(gt_match.group(1))


def compute_split_conservation(
    pft_output_dir: Path, class_count_dir: Path, block_size: int
) -> list[dict[str, object]]:
    rows_out: list[dict[str, object]] = []
    split_files = sorted(pft_output_dir.glob("pft*-pft*_landtype*_nalcms_*_in_daymet.nc"))
    for split_file in split_files:
        landtype_id = parse_landtype_id(split_file.name)
        if landtype_id is None:
            continue
        source_tif = class_count_dir / f"landtype{landtype_id}_count_in_namask.tif"
        if not source_tif.exists():
            rows_out.append({"split_file": split_file.name, "status": "missing source count raster"})
            continue
        with Dataset(split_file) as ds, rasterio.open(source_tif) as src:
            pft_vars = [name for name in ds.variables if name.startswith("pft") and name.endswith("_count")]
            temp_var = ds.variables.get("AvgTemp")
            if len(pft_vars) != 2:
                rows_out.append({"split_file": split_file.name, "status": f"expected 2 PFT variables, found {len(pft_vars)}"})
                continue
            height = ds.variables[pft_vars[0]].shape[0]
            width = ds.variables[pft_vars[0]].shape[1]
            bounds = parse_bounds(getattr(ds, "temperature_bounds", ""))
            lower, upper = bounds if bounds is not None else (math.nan, math.nan)
            checked = failures = valid_source_cells = transition_cells = cold_cells = warm_cells = 0
            max_residual = 0
            source_total = pft_total = 0
            temp_values = []
            for start, stop in rows(height, block_size):
                window = rasterio.windows.Window(0, start, width, stop - start)
                source = src.read(1, window=window).astype(np.int64)
                source_valid = source >= 0
                source_nonzero = source > 0
                pft_a = as_array(ds.variables[pft_vars[0]][start:stop, :]).astype(np.int64)
                pft_b = as_array(ds.variables[pft_vars[1]][start:stop, :]).astype(np.int64)
                pft_sum = pft_a + pft_b
                residual = pft_sum[source_valid] - source[source_valid]
                if residual.size:
                    abs_residual = np.abs(residual)
                    checked += int(abs_residual.size)
                    failures += int(np.sum(abs_residual != 0))
                    max_residual = max(max_residual, int(np.max(abs_residual)))
                source_total += int(np.sum(np.where(source_valid, source, 0)))
                pft_total += int(np.sum(np.where(source_valid, pft_sum, 0)))
                valid_source_cells += int(np.sum(source_nonzero))
                if temp_var is not None:
                    temp = as_array(temp_var[start:stop, :])
                    mask = source_nonzero & np.isfinite(temp)
                    if np.any(mask):
                        temp_values.append(temp[mask])
                        if math.isfinite(lower) and math.isfinite(upper):
                            cold_cells += int(np.sum(mask & (temp <= lower)))
                            warm_cells += int(np.sum(mask & (temp > upper)))
                            if lower != upper:
                                transition_cells += int(np.sum(mask & (temp > lower) & (temp <= upper)))
            temp_all = np.concatenate(temp_values) if temp_values else np.array([])
            temp_stats = finite_stats(temp_all)
            rows_out.append(
                {
                    "split_file": split_file.name,
                    "landtype": landtype_id,
                    "pft_variables": "+".join(pft_vars),
                    "lower_c": fmt(lower),
                    "upper_c": fmt(upper),
                    "cells_checked": checked,
                    "source_nonzero_cells": valid_source_cells,
                    "residual_failures": failures,
                    "residual_failure_percent_source_cells": fmt(
                        100.0 * failures / valid_source_cells if valid_source_cells else math.nan
                    ),
                    "max_abs_residual_pixels": max_residual,
                    "source_count_total": source_total,
                    "pft_count_total": pft_total,
                    "count_total_difference": pft_total - source_total,
                    "count_total_difference_percent": fmt(
                        100.0 * (pft_total - source_total) / source_total if source_total else math.nan
                    ),
                    "cold_cells": cold_cells,
                    "transition_cells": transition_cells,
                    "warm_cells": warm_cells,
                    "mtco_min_c": fmt(temp_stats["min"]),
                    "mtco_mean_c": fmt(temp_stats["mean"]),
                    "mtco_max_c": fmt(temp_stats["max"]),
                    "status": "ok",
                }
            )
    return rows_out


def write_markdown_summary(path: Path, metrics: list[Metric], split_rows: list[dict[str, object]]) -> None:
    with path.open("w") as f:
        f.write("# Internal Validation Summary\n\n")
        f.write("## Key Metrics\n\n")
        f.write("| Category | Check | Value | Units | Notes |\n")
        f.write("|---|---:|---:|---|---|\n")
        for m in metrics:
            f.write(f"| {m.category} | {m.check} | {m.value} | {m.units} | {m.notes} |\n")
        f.write("\n## Climate Split Conservation\n\n")
        if not split_rows:
            f.write("No split files found.\n")
            return
        fields = [
            "landtype",
            "pft_variables",
            "lower_c",
            "upper_c",
            "source_nonzero_cells",
            "residual_failures",
            "residual_failure_percent_source_cells",
            "max_abs_residual_pixels",
            "mtco_min_c",
            "mtco_mean_c",
            "mtco_max_c",
        ]
        f.write("| " + " | ".join(fields) + " |\n")
        f.write("|" + "|".join(["---"] * len(fields)) + "|\n")
        for row in split_rows:
            f.write("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument(
        "--final-nc",
        type=Path,
        default=DEFAULT_FINAL_NC,
        help="Final surfdata NetCDF for closure checks (default: Great Lakes corrected c260128 file)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "results")
    parser.add_argument("--row-block", type=int, default=256)
    parser.add_argument("--tolerance", type=float, default=1e-3)
    parser.add_argument("--skip-class-count-closure", action="store_true")
    args = parser.parse_args()

    data_root = args.data_root
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    final_nc = args.final_nc
    landunit_nc = data_root / "dataProduct_DOI" / "land_veg_urban_lake_glacier_percentage.nc"
    pft_output_dir = data_root / "ELM_PFTs" / "ELM_PFT_output"
    class_count_dir = data_root

    required = [final_nc, landunit_nc, pft_output_dir]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required inputs:\n" + "\n".join(missing))

    metrics: list[Metric] = []
    metrics.extend(compute_final_product_checks(final_nc, args.row_block, args.tolerance))
    if args.skip_class_count_closure:
        metrics.append(Metric("intermediate counts", "class-count closure", "skipped"))
    else:
        metrics.extend(compute_intermediate_count_closure(landunit_nc, class_count_dir, args.row_block))

    split_rows = compute_split_conservation(pft_output_dir, class_count_dir, args.row_block)

    write_metrics(output_dir / "summary_metrics.csv", metrics)
    write_table(
        output_dir / "climate_split_conservation.csv",
        [
            "split_file",
            "landtype",
            "pft_variables",
            "lower_c",
            "upper_c",
            "cells_checked",
            "source_nonzero_cells",
            "residual_failures",
            "residual_failure_percent_source_cells",
            "max_abs_residual_pixels",
            "source_count_total",
            "pft_count_total",
            "count_total_difference",
            "count_total_difference_percent",
            "cold_cells",
            "transition_cells",
            "warm_cells",
            "mtco_min_c",
            "mtco_mean_c",
            "mtco_max_c",
            "status",
        ],
        split_rows,
    )
    write_markdown_summary(output_dir / "internal_validation_summary.md", metrics, split_rows)
    print(f"Wrote validation outputs to {output_dir}")


if __name__ == "__main__":
    main()
