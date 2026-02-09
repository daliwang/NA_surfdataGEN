import argparse
import os
import numpy as np
from netCDF4 import Dataset
import matplotlib.pyplot as plt

INPUT_FILE = "landtype3_nalcms_Tropical_evergreen_in_daymet.nc"
ALIGNED_TEMP_FILE = "aligned_temp_to_large_nalcms_mask.nc"
OUTPUT_DIR = "ELM_PFT_output_split_18C"
PFT_WARM = "pft4"
PFT_COOL = "pft5"
THRESHOLD_C = 18


def write_pft_file(output_dir, input_file, pft_name, pft_count, threshold_c):
    os.makedirs(output_dir, exist_ok=True)
    output_file = f"{output_dir}/{pft_name}_{input_file}"
    with Dataset(output_file, "w", format="NETCDF4") as dst:
        dst.createDimension("y", pft_count.shape[0])
        dst.createDimension("x", pft_count.shape[1])
        var = dst.createVariable(f"{pft_name}_count", "i4", ("y", "x"), zlib=True, complevel=5)
        var[:, :] = pft_count
        var.long_name = f"{pft_name} count based on AvgTemp split"
        var.units = "count"
        dst.setncattr("original_landtype_file", input_file)
        dst.setncattr("temperature_bounds", f"<= {threshold_c} C vs > {threshold_c} C")
    print(f"Saved {output_file}")


def plot_pft_counts(output_dir, pft_warm, pft_cool, threshold_c):
    os.makedirs(output_dir, exist_ok=True)
    plots = [
        ("pft4_count.png", pft_warm, f"PFT4 count (AvgTemp > {threshold_c} C)"),
        ("pft5_count.png", pft_cool, f"PFT5 count (AvgTemp <= {threshold_c} C)"),
    ]
    for filename, data, title in plots:
        plt.figure(figsize=(8, 6))
        img = plt.imshow(data, origin="upper")
        plt.colorbar(img, label="count")
        plt.title(title)
        plt.tight_layout()
        out_path = f"{output_dir}/{filename}"
        plt.savefig(out_path, dpi=150)
        plt.close()
        print(f"Saved {out_path}")


def split_tropical_evergreen_by_temp(threshold_c, plot):
    with Dataset(f"../landtypes_count/{INPUT_FILE}") as nc:
        count = nc.variables["landtype_count"][:]
    with Dataset(ALIGNED_TEMP_FILE) as nc:
        avg_temp = nc.variables["AvgTemp"][:]

    valid = (~np.isnan(avg_temp)) & (count >= 0)
    pft_warm = np.zeros_like(count, dtype=int)
    pft_cool = np.zeros_like(count, dtype=int)

    mask_cool = valid & (avg_temp <= threshold_c)
    mask_warm = valid & (avg_temp > threshold_c)
    pft_cool[mask_cool] = count[mask_cool]
    pft_warm[mask_warm] = count[mask_warm]

    write_pft_file(OUTPUT_DIR, INPUT_FILE, PFT_WARM, pft_warm, threshold_c)
    write_pft_file(OUTPUT_DIR, INPUT_FILE, PFT_COOL, pft_cool, threshold_c)
    if plot:
        plot_pft_counts(OUTPUT_DIR, pft_warm, pft_cool, threshold_c)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Split tropical evergreen landtype into PFTs by temperature threshold."
    )
    parser.add_argument(
        "--threshold-c",
        type=float,
        default=THRESHOLD_C,
        help="Temperature threshold in C (default: 18).",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Save PNG plots for pft4 and pft5 counts.",
    )
    args = parser.parse_args()
    split_tropical_evergreen_by_temp(args.threshold_c, args.plot)
