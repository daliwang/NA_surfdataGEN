#!/usr/bin/env python3
"""
Generate a high-resolution Figure 3 reprojection map from the NALCMS GeoTIFF.

Default input (outside git; see NALCMS2Daymet_ELM workflow):
  NA_surfdataGEN/NADaymet/entire_domain/nalcms2daymet_hcompressed.tif

Default output:
  E3SM_1km_data_preparation/reprojection.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from scipy.ndimage import binary_dilation, binary_erosion

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_INPUT = Path(
    "/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/"
    "NADaymet/entire_domain/nalcms2daymet_hcompressed.tif"
)
DEFAULT_OUTPUT = REPO_ROOT / "E3SM_1km_data_preparation" / "reprojection.png"
NODATA_VALUE = 127
BACKGROUND_VALUES = {0, NODATA_VALUE}
BACKGROUND_RGB = np.array([0.82, 0.82, 0.82], dtype=np.float32)
BOUNDARY_RGB = np.array([0.20, 0.20, 0.20], dtype=np.float32)


def load_downsampled_classes(path: Path, max_width: int) -> np.ndarray:
    with rasterio.open(path) as ds:
        scale = max(1, int(np.ceil(ds.width / max_width)))
        out_h = int(np.ceil(ds.height / scale))
        out_w = int(np.ceil(ds.width / scale))
        data = ds.read(
            1,
            out_shape=(out_h, out_w),
            resampling=Resampling.nearest,
        )
        colormap = ds.colormap(1)
    if colormap is None:
        raise ValueError(f"No embedded colormap found in {path}")
    return data, colormap


def domain_boundary_mask(domain: np.ndarray, width: int = 5) -> np.ndarray:
    domain = domain.astype(bool)
    edge = domain & ~binary_erosion(domain)
    if width > 1:
        edge = binary_dilation(edge, iterations=width - 1)
    return edge


def classes_to_rgb(
    data: np.ndarray,
    colormap: dict[int, tuple[int, int, int, int]],
    boundary_width: int,
) -> np.ndarray:
    rgb = np.full((*data.shape, 3), BACKGROUND_RGB, dtype=np.float32)
    domain = data != NODATA_VALUE

    for class_id, rgba in colormap.items():
        if class_id in BACKGROUND_VALUES:
            continue
        mask = data == class_id
        if not np.any(mask):
            continue
        rgb[mask] = np.array(rgba[:3], dtype=np.float32) / 255.0

    boundary = domain_boundary_mask(domain, width=boundary_width)
    rgb[boundary] = BOUNDARY_RGB
    return rgb


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate high-resolution NALCMS reprojection figure.")
    parser.add_argument("--input-file", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-file", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--max-width",
        type=int,
        default=4800,
        help="Maximum image width in pixels (full raster is downsampled for plotting).",
    )
    parser.add_argument(
        "--boundary-width",
        type=int,
        default=5,
        help="Outline thickness in pixels for the reprojected-domain boundary.",
    )
    args = parser.parse_args()

    if not args.input_file.is_file():
        print(f"Input GeoTIFF not found: {args.input_file}", flush=True)
        print(
            "Expected the reprojected NALCMS raster produced by the NALCMS2Daymet_ELM workflow:",
            flush=True,
        )
        print("  NA_surfdataGEN/NADaymet/entire_domain/nalcms2daymet_hcompressed.tif", flush=True)
        return 1

    data, colormap = load_downsampled_classes(args.input_file, args.max_width)
    rgb = classes_to_rgb(data, colormap, boundary_width=args.boundary_width)
    rgba = np.dstack([rgb, np.ones(data.shape, dtype=np.float32)])

    height_px, width_px = rgb.shape[:2]
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((rgba * 255).astype(np.uint8), mode="RGBA").save(args.output_file)
    print(f"Wrote {args.output_file} ({width_px} x {height_px} px)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
