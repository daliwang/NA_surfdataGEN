import sys
import rasterio
import numpy as np

# Define the mapping of class IDs to RGB values and short names
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

def separate_class(input_geotiff):
    # Open the input GeoTIFF file
    with rasterio.open(input_geotiff) as src:
        data = src.read(1)  # Read the first band
        meta = src.meta

#    # Create an empty output array for RGB data
#    output_data = np.zeros((data.shape[0], data.shape[1], 3), dtype=np.uint8)

    # Loop through each class from 1 to 19
    for class_id, (rgb, short_name) in class_mapping.items():

        # Create an empty output array for RGB data
        output_data = np.zeros((data.shape[0], data.shape[1], 3), dtype=np.uint8)

        # Create a mask for the specific class
        mask = (data == class_id).astype(np.uint8)

        # Assign the RGB values where the mask is applied
        output_data[mask == 1, 0] = rgb[0]  # Red channel
        output_data[mask == 1, 1] = rgb[1]  # Green channel
        output_data[mask == 1, 2] = rgb[2]  # Blue channel

        # Update metadata for output
        meta.update({
            'dtype': 'uint8',
            'count': 3,  # Since we're going to write 3 bands (RGB)
            'nodata': 0
        })

        # Create class file name
        class_filename = f'nalcms_{short_name}.tiff'

        # Write the output GeoTIFF (only once, for the final RGB image)
        with rasterio.open(class_filename, 'w', **meta) as dst:
            dst.write(output_data.transpose(2, 0, 1))  # Write with band order (C, H, W)

        print(f'Saved: {class_filename}')

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 separate_class.py input_geotiff")
        sys.exit(1)

    input_geotiff = sys.argv[1]
    separate_class(input_geotiff)
