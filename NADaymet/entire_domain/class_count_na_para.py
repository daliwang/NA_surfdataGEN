import rasterio
import numpy as np
import argparse
import re
from shapely.geometry import box
from rasterio.mask import mask

def count_landtype_in_mask(mask_path, landtype_path, landtype_value):
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
            output_data = np.full((mask_height, mask_width), -1, dtype=np.int16)

            step = 0
            print(f'Start processing first gridcells')  
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

                        step += 1
                        if step % 1000 == 0:
                            print(f'Processed {step} gridcells')    

        # Update metadata for output
        output_meta = mask_src.meta.copy()
        output_meta.update({
            'dtype': 'int16',
            'count': 1,
            'nodata': -1
        })
        
        # Save the output data to a new GeoTIFF file
        output_path = f'/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/landtype{landtype_value}_count_in_namask.tif'
        with rasterio.open(output_path, 'w', **output_meta) as dst:
            dst.write(output_data, 1)
        
        print(f'Saved: {output_path}')

def main():
    parser = argparse.ArgumentParser(description='Count landtype in mask.')
    parser.add_argument('input_geotiff', type=str, help='Input GeoTIFF file in the format nclmcs_<class_id>_<short_name>.tif')
    args = parser.parse_args()

    # Parse the class_id from the input filename
    match = re.match(r'nalcms_(\d+)_(.+)\.tif', args.input_geotiff)
    if not match:
        raise ValueError('Input GeoTIFF filename must be in the format nalcms_<class_id>_<short_name>.tif')
    
    class_id = int(match.group(1))
    print(f'Parsed class_id: {class_id}')

    # Define the mask path
    data_path = '/Users/7xw/Documents/Work/ELM_ECP/kiloCraft_dev/NA_surfdataGEN/NADaymet/entire_domain/'
    mask_path = data_path + 'na_mask.tif'
    landtype_path = data_path + args.input_geotiff

    # Call the function with the parsed class_id
    count_landtype_in_mask(mask_path, landtype_path, class_id)

if __name__ == '__main__':
    main()