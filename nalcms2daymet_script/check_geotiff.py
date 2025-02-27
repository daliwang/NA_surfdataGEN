import rasterio
import numpy as np
import sys
import re

def count_pixels(tif_file, value, block_size=25000):
    count = 0
    step_count = 0
    with rasterio.open(tif_file) as src:
        height, width = src.height, src.width
        
        for row_start in range(0, height, block_size):
            row_end = min(row_start + block_size, height)
            for col_start in range(0, width, block_size):
                col_end = min(col_start + block_size, width)
                
                window = rasterio.windows.Window(col_start, row_start, col_end - col_start, row_end - row_start)
                data_block = src.read(1, window=window)
                
                count += np.sum(data_block == value)
                step_count += 1
                if step_count % 5 == 0:
                    print(f"Step {step_count}: Current count of pixels with value {value}: {count}")



    return count

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 count_pixels.py <tif_file>")
        sys.exit(1)

    tif_file = sys.argv[1]
    value_to_check = int(re.search(r'nalcms_(\d+)_', tif_file).group(1))
    count = count_pixels(tif_file, value_to_check)
    print(f"Number of pixels with value {value_to_check}: {count}")


