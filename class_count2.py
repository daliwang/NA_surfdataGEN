import rasterio
import numpy as np
from rasterstats import zonal_stats
from shapely.geometry import box
from rasterio.mask import mask


def count_landtype_in_mask(mask_path, landtype_path, landtype_value=14):

    # Open the mask GeoTIFF file
    with rasterio.open(mask_path) as mask_src:
        mask_data = mask_src.read(1)
        mask_transform = mask_src.transform
        mask_crs = mask_src.crs

        # Open the landtype GeoTIFF file
        with rasterio.open(landtype_path) as landtype_src:
            landtype_data = landtype_src.read(1)
            landtype_transform = landtype_src.transform
            landtype_crs = landtype_src.crs

            # Initialize the output array with -1 for masked gridcells
            mask_height, mask_width = mask_data.shape
            output_data = np.full((mask_height, mask_width), -1, dtype=np.int32)

            # Create a mask polygon for each grid cell
            for row in range(mask_height):
                for col in range(mask_width):
                    if mask_data[row, col] == 1:
                        x_min, y_min = mask_transform * (col, row)
                        x_max, y_max = mask_transform * (col + 1, row + 1)
                        polygon = box(x_min, y_min, x_max, y_max)
                        
                        # Mask the landtype data with the polygon
                        out_image, out_transform = mask(landtype_src, [polygon], crop=True)
                        out_image = out_image[0]
                        
                        # Count the number of pixels with the specified landtype value
                        count = np.sum(out_image == landtype_value)
                        output_data[row, col] = count



        # Update metadata for output
        output_meta = mask_src.meta.copy()
        output_meta.update({
            'dtype': 'int32',
            'count': 1,
            'nodata': -1
        })
        
        # Save the output data to a new GeoTIFF file
        output_path = '/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/landtype_count_in_mask2.tif'
        with rasterio.open(output_path, 'w', **output_meta) as dst:
            dst.write(output_data, 1)
        
        print(f'Saved: {output_path}')

# Example usage
data_path='/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/'
mask_path = data_path + 'testMask.tif'
landtype_path = data_path +'class_14.tiff'
count_landtype_in_mask(mask_path, landtype_path)