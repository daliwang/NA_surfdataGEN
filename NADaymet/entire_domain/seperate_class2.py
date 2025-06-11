import sys
import rasterio
import numpy as np
from rasterio.windows import Window
from scipy.sparse import csr_matrix
from rasterio.enums import Compression

# Define the mapping of class IDs to grayscale values
class_mapping = {
    1: 'Temperate_needleleaf',
    2: 'Taiga_needleleaf',
    3: 'Tropical_evergreen',
    4: 'Tropical_deciduous',
    5: 'Temperate_deciduous',
    6: 'Mixed_forrest',
    7: 'Tropical_shrub',
    8: 'Temperate_shrub',
    9: 'Tropical_grass',
    10: 'Temperate_grass',
    11: 'Polar_shrub_moss',
    12: 'Polar_grass_moss',
    13: 'Polar_barren_moss',
    14: 'Wetland',
    15: 'Cropland',
    16: 'Barren_land',
    17: 'Urban',
    18: 'Water',
    19: 'Snow_Ice',
}

def separate_class(input_geotiff):
    # Open the input GeoTIFF file
    with rasterio.open(input_geotiff) as src:
        meta = src.meta
        height, width = src.height, src.width 
        block_size = 4096  # Adjust this size based on your RAM size
        
        # Loop through each class from 1 to 19
        for class_id, short_name in class_mapping.items():
            print("class_id is ", class_id)

            # Create a sparse matrix for the output data of shape (height, width)
            output_data = csr_matrix((height, width), dtype=np.uint8)
            print("Created sparse matrix for class: ", short_name)

            # Process data in chunks
            for row_start in range(0, height, block_size):
                row_end = min(row_start + block_size, height)
                for col_start in range(0, width, block_size):
                    col_end = min(col_start + block_size, width)

                    window = Window(col_start, row_start, col_end - col_start, row_end - row_start)
                    data_block = src.read(1, window=window)  # Read in chunks

                    # Create a mask for the specific class
                    mask = (data_block == class_id)

                    # Assign the class ID to the sparse matrix where the mask is applied
                    output_data[row_start:row_end, col_start:col_end][mask] = class_id
            
            # Now we'll save the sparse matrix data into a GeoTIFF file
            output_geoTIFF_path = f"{short_name}.tif"
            with rasterio.open(output_geoTIFF_path, 'w', driver='GTiff',
                               height=output_data.shape[0],
                               width=output_data.shape[1],
                               count=1,
                               dtype='uint8',
                               crs=meta['crs'],
                               transform=meta['transform'],
                               compress='lzw') as dst:
                dst.write(output_data.toarray(), 1)  # Convert sparse matrix to dense for saving
            print(f"Saved {output_geoTIFF_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 separate_class22.py input_geotiff")
        sys.exit(1)

    input_geotiff = sys.argv[1]
    separate_class(input_geotiff)
