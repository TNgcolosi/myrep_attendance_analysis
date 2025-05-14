# -*- coding: utf-8 -*-
"""
Created on Mon Jan 27 17:46:04 2025

@author: Thandi
"""

import geopandas as gpd

# Path to the shapefile (.shp file)
shapefile_path = "ward boudaries/SA_Wards2020.shp"

# Load the shapefile using GeoPandas
gdf = gpd.read_file(shapefile_path)

# Display the first few rows to understand the data
print(gdf.head())

# Check the structure of the dataset
print("\nColumns in the dataset:")
print(gdf.columns)

# Check the Coordinate Reference System (CRS)
print("\nCoordinate Reference System (CRS):")
print(gdf.crs)
 
# Plot a quick visualization to see the spatial data
gdf.plot()
