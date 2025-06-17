#!/bin/bash

# Search for all files in the format nalcms_[0-10]_<string>.tif
find . -type f -regex '.*nalcms_1[1-3]_[^/]*\.tif' | while read -r tif_file; do
    # Pass each tif file to python3 check_geotiff.py and redirect the output to check_tiff.log
    python3 check_geotiff.py "$tif_file" >> check_tiff_11_12_13.log 2>&1
done


