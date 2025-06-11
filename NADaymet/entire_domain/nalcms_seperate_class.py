import sys
import rasterio
import numpy as np
from scipy import sparse
from rasterio.windows import Window
from rasterio.enums import Compression

# Define the mapping of class IDs to RGB values and short names

''' 
class_mapping = {
    1: ((0, 61, 0), 'Temperate_needleleaf'),
    2: ((148, 156, 112), 'Taiga_needleleaf'),
    3: ((0, 99, 0), 'Tropical_evergreen'),
    4: ((30, 171, 5), 'Tropical_deciduous'),
    5: ((20, 140, 61), 'Temperate_deciduous'),
    6: ((92, 117, 43),   'Mixed_forrest'),
    7: ((179, 158, 43),  'Tropical_shrub'),
    8: ((179, 138, 51), 'Temperate_shrub'),
    9: ((232, 220, 94),   'Tropical_grass'),
    10: ((225, 207, 138), 'Temperate_grass'),
    11: ((156, 117, 84),  'Polar_shrub_moss'),
    12: ((186, 212, 143),  'Polar_grass_moss'),
    13: ((64, 138, 112), 'Polar_barren_moss'),
    14: ((107, 163, 138), 'Wetland'),
    15: ((230, 174, 102), 'Cropland'),
    16: ((168, 171, 174), 'Barren_land'),
    17: ((220, 33, 38), 'Urban'),
    18: ((76, 112, 163), 'Water'),
    19: ((255, 250, 255), 'Snow_Ice'),
}

class_mapping = {
    1: ('Temperate_needleleaf'),
    2: ('Taiga_needleleaf'),
    3: ('Tropical_evergreen'),
    4: ('Tropical_deciduous'),
    5: ('Temperate_deciduous'),
    6: ('Mixed_forrest'),
    7: ('Tropical_shrub'),
    8: ('Temperate_shrub'),
    9: ('Tropical_grass'),
    10: ('Temperate_grass'),
    11: ('Polar_shrub_moss'),
    12: ('Polar_grass_moss'),
    13: ('Polar_barren_moss'),
    14: ('Wetland'),
    15: ('Cropland'),
    16: ('Barren_land'),
    17: ('Urban'),
    18: ('Water'),
    19: ('Snow_Ice'),
}
'''
class_mapping = {
    1: ('Temperate_needleleaf'),
}

def separate_class(input_geotiff):
    # Open the input GeoTIFF file
    with rasterio.open(input_geotiff) as src:
        meta = src.meta
        height, width = src.height, src.width 
        block_size = 20000  # Adjust this size based on your RAM size
        
        # Loop through each class from 1 to 19
        for class_id, (short_name) in class_mapping.items():
            print("Processing class_id: ", class_id)
            block_count=0
           # Create an empty output array
            output_sparse_data = sparse.lil_matrix((height, width), dtype=np.uint8)
            #output_data = np.zeros((height, width, 3), dtype=np.uint8)
            print("the shape of output data: ",output_sparse_data.shape)

            # Process data in chunks
            for row_start in range(0, height, block_size):
                row_end = min(row_start + block_size, height)
                for col_start in range(0, width, block_size):
                    col_end = min(col_start + block_size, width)

                    window = Window(col_start, row_start, col_end - col_start, row_end - row_start)
                    data_block = src.read(1, window=window)  # Read in chunks

                    # Debug prints to check data_block and class_id
                    print(f"Data block shape: {data_block.shape}")
                    print(f"Unique values in data block: {np.unique(data_block)}")
                    print(f"Class ID: {class_id}")

                    # Create a mask for the specific class
                    mask = (data_block == class_id)
                    print(f"Mask shape: {mask.shape}")
                    print(f"Mask sum: {np.sum(mask)}")  # Number of True values in the mask


                    # Assign the RGB values where the mask is applied
                    #output_data[row_start:row_end, col_start:col_end, 0][mask] = rgb[0]  # Red channel
                    #output_data[row_start:row_end, col_start:col_end, 1][mask] = rgb[1]  # Green channel
                    #output_data[row_start:row_end, col_start:col_end, 2][mask] = rgb[2]  # Blue channel

                    # Assign the class_id where the mask is applied
                    rows, cols = np.nonzero(mask)
                    output_sparse_data[rows + row_start, cols + col_start] = class_id

                    print(f"Non-zero values in output_sparse_data: {output_sparse_data.nnz}")
                    block_count=block_count+1

                    if ((block_count%5) == 0):
                        print("Processiing ",block_count)
                    
            # Convert the sparse matrix to a dense format for writing.
            output_data = output_sparse_data.toarray()
            print(f"Non-zero values in output_data: {np.count_nonzero(output_data)}")
            print(f"Unique values in output_data: {np.unique(output_data)}")


            # Update metadata for output
            output_meta = meta.copy()
            output_meta.update({
                'dtype': 'uint8',
                'count': 1,  
                'nodata': 127,
                'compress': Compression.lzw  # Using LZW compression
            })

            # Create class file name
            class_filename = f'nalcms_{class_id}_{short_name}.tif'

            # Write the output GeoTIFF (only once, for the final RGB image)
            with rasterio.open(class_filename, 'w', **output_meta) as dst:
                dst.write(output_data, 1)
            print(f'Saved: {class_filename}')

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 separate_class.py input_geotiff")
        sys.exit(1)

    input_geotiff = sys.argv[1]
    separate_class(input_geotiff)
