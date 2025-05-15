# -*- coding: utf-8 -*-
"""
Created on Mon Jan 27 17:46:04 2025

@author: Thandi
"""
import os
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import geopy

from geopy.geocoders import Nominatim
import folium
from folium.features import GeoJson, GeoJsonTooltip, GeoJsonPopup
import fiona
import pyproj
from pyproj import CRS
import pyogrio
from folium.plugins import Search
from shapely.geometry import Point
import plotly.express as px
import base64
from io import BytesIO
import re
import sqlite3

#%%
os.environ["PROJ_LIB"] = r"C:\Users\Thandi\anaconda3\envs\my_rep\Library\share\proj"

# Path to the shapefile (.shp file)
shapefile_path = "C:/Users/Thandi/Documents/GitHub/my rep/ward boundaries/SA_Wards2020.shp"

# Load the shapefile using GeoPandas
#gdf = gpd.read_file(shapefile_path, engine="pyogrio")

gdf = gpd.GeoDataFrame(pyogrio.read_dataframe(shapefile_path))
# Initialize the geocoder
geolocator = Nominatim(user_agent="ward_locator")
#%%
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
#%%
# Path to the SQLite database
db_path = "council_data.db"
connection = sqlite3.connect(db_path)
# Connect to the database and load the attendance data into a DataFrame
with sqlite3.connect(db_path) as connection:
    # Load attendance data into a DataFrame
    df = pd.read_sql("SELECT * FROM merged_data", connection)
    
'''excel_file_path = 'council minutes 2024/test/attendance_seed_matched.xlsx'
df = pd.read_excel(excel_file_path, sheet_name="Merged Data")'''
#%%
# Inspect both datasets to ensure column names match
print("GeoDataFrame Columns:", gdf.columns)
print("Excel DataFrame Columns:", df.columns)
#%%
# Ensure the 'ward' column is present in both and has the same type
# Rename columns if necessary
df.rename(columns={"WARD ID": "WardID"}, inplace=True)
df.rename(columns={"WARD NUMBER": "WardNo"}, inplace=True)
df['WardID'] = df['WardID'].fillna(0).astype(int)

gdf = gdf[gdf['DistrictCo'] == 'ETH']
gdf['WardID'] = gdf['WardID'].astype(int)

gdf_pic = gdf.merge(df, on="WardNo", how="inner")
''' get gdf_pic and merged_gdf to have the same columns, stack them on top of each other and visualise '''

# Merge the GeoDataFrame and DataFrame on the 'ward' column
complete_gdf = gdf.merge(df, on="WardID", how="inner")

#complete_gdf = pd.concat([gdf_pic, merged_gdf], ignore_index=True)

complete_gdf.plot()

#%%
complete_gdf['WardNo'] = complete_gdf['WardNo_x'].fillna(complete_gdf['WardNo_y'])
#complete_gdf['WardID_x'] = complete_gdf['WardID'].fillna(complete_gdf['WardID_x']).astype(int)
complete_gdf.drop(['extracted_initials', 'WardNo_y', 'WardNo_x'], axis=1, inplace=True)
complete_gdf = complete_gdf.sort_values(by='WardNo', ascending=True)

#%%

# Display the first few rows of the merged GeoDataFrame
#print(merged_gdf.head())

# Check if the merge was successful
#print(f"Number of rows after merge: {len(merged_gdf)}")

# Save the merged GeoDataFrame to a new shapefile (optional)
#merged_gdf.to_file("councillor_attendance.shp")

#merged_gdf.plot()
#%%
# Check if the 'attendance rating' column exists
if 'attendance_percentage' in complete_gdf.columns:
    # Plot the GeoDataFrame, coloring wards by 'attendance rating'
    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    complete_gdf.plot(
        column='attendance_percentage',  # Column to color-code
        cmap='viridis',  # Colormap (you can choose others like 'plasma', 'coolwarm', etc.)
        legend=True,  # Add a legend
        legend_kwds={'label': "Attendance Rating (%)"},  # Legend label
        ax=ax  # Add to the current axis
    )
    
    # Add a title and labels
    ax.set_title("Wards Color-Coded by Attendance Rating", fontsize=15)
    ax.set_axis_off()  # Remove axes for a clean map look

    # Show the plot
    plt.show()
else:
    print("The 'attendance rating' column is missing from the GeoDataFrame.")
#%%

# Define a helper function to determine fill color based on attendance rating
def get_color(attendance):
    if attendance is None:
        return "#d9d9d9"  # Grey for missing values
    elif attendance < 20:
        return "#f03b20"  # Red
    elif attendance < 40:
        return "#feb24c"  # Orange
    elif attendance < 60:
        return "#ffeda0"  # Yellow
    elif attendance < 80:
        return "#31a354"  # Green
    else:
        return "#006837"  # Dark Green
    
complete_gdf["Date"] = complete_gdf["Date"].astype(str)

# Convert to EPSG:4326 (needed for Folium)
complete_gdf = complete_gdf.to_crs(epsg=4326)

# Center the map around the dataset's centroid
map_center = [complete_gdf.geometry.centroid.y.mean(), complete_gdf.geometry.centroid.x.mean()]

# Create a Folium map
m = folium.Map(location=map_center, zoom_start=10)

# Convert the GeoDataFrame to GeoJSON format for Folium
geojson_data = complete_gdf.__geo_interface__

# Define popup and tooltip content
popup = GeoJsonPopup(
    fields=['FIRSTNAME(S)', "initials", 'surname', "attendance_percentage", 'District', "WardNo", "POLITICAL PARTY"],
    aliases=["Councillor Name:", "Initials:", "Last Name:", "Attendance (%):", "District:" , "Ward ID:", "Party:"],
    localize=True,
    labels=True,
    style="font-size: 12px;"
)

tooltip = GeoJsonTooltip(
    fields=['FIRSTNAME(S)', "initials", 'surname', "attendance_percentage", 'District', "WardNo", "POLITICAL PARTY"],
    aliases=["Councillor Name:", "Initials:", "Last Name:", "Attendance (%):", "District:" , "Ward ID:", "Party:"],
    localize=True,
    sticky=True
)

# Add the GeoJSON layer with a choropleth
choropleth = folium.Choropleth(
    geo_data=geojson_data,
    name="choropleth",
    data=complete_gdf,
    columns=["WardID", "attendance_percentage"],
    key_on="feature.properties.WardID",
    fill_color="PuBuGn",
    fill_opacity=0.7,
    line_opacity=0.5,
    nan_fill_color="grey",  # If NaN values exist
    legend_name="Attendance Rating (%)",
).add_to(m)

# Add GeoJson Layer for Interactivity
geojson_layer = folium.GeoJson(
    geojson_data,
    name="Ward Boundaries",
    tooltip=tooltip,
).add_to(m)

# ✅ Add Search Box for Address Input
search = Search(
    layer=geojson_layer,
    geom_type="Polygon",
    placeholder="Search Ward...",
    search_label="WardNo",
    collapsed=False,
).add_to(m)


# Add a legend
legend_html = """
<div style="position: fixed; bottom: 50px; left: 50px; width: 200px; height: 150px; 
            background-color: white; z-index:9999; font-size:14px; border:1px solid grey; 
            padding: 10px;">
    <strong>Attendance Rating Legend</strong><br>
    <i style="background: #f03b20; width: 10px; height: 10px; float: left; margin-right: 5px;"></i> 0-20%<br>
    <i style="background: #feb24c; width: 10px; height: 10px; float: left; margin-right: 5px;"></i> 21-40%<br>
    <i style="background: #ffeda0; width: 10px; height: 10px; float: left; margin-right: 5px;"></i> 41-60%<br>
    <i style="background: #31a354; width: 10px; height: 10px; float: left; margin-right: 5px;"></i> 61-80%<br>
    <i style="background: #006837; width: 10px; height: 10px; float: left; margin-right: 5px;"></i> 81-100%<br>
</div>
"""

# ✅ Add JavaScript Address Search Bar for Geocoding
search_html = """
<div style="position: absolute; top: 10px; left: 50px; z-index: 1000; background: white; padding: 10px; border-radius: 5px; box-shadow: 2px 2px 5px grey;">
    <input type="text" id="address_input" placeholder="Enter Address..." style="width: 250px; padding: 5px;"/>
    <button onclick="searchAddress()" style="padding: 5px;">Search</button>
</div>

<script>
function searchAddress() {
    var address = document.getElementById('address_input').value;
    var url = "https://nominatim.openstreetmap.org/search?format=json&q=" + encodeURIComponent(address);
    
    fetch(url)
    .then(response => response.json())
    .then(data => {
        if (data.length > 0) {
            var lat = data[0].lat;
            var lon = data[0].lon;
            L.marker([lat, lon]).addTo(map).bindPopup("📍 " + address).openPopup();
            map.setView([lat, lon], 12);
        } else {
            alert("❌ Address not found. Try another.");
        }
    })
    .catch(error => console.error("Error:", error));
}
</script>
"""
#%%
 #✅ Function to Geocode and Add a Marker for the Address
def add_address_marker(address, map_object):
    location = geolocator.geocode(address, timeout=10)
    if not location:
        print(f"❌ Address '{address}' not found.")
        return None

    point = Point(location.longitude, location.latitude)
    ward = complete_gdf[complete_gdf.geometry.contains(point)]
    if ward.empty:
        ward = complete_gdf[complete_gdf.geometry.intersects(point)]

    if ward.empty:
        print("❌ No exact match, finding nearest ward...")
        nearest_ward_idx = complete_gdf.distance(point).idxmin()
        ward = complete_gdf.loc[[nearest_ward_idx]]

    ward_info = ward.iloc[0]
    popup_text = f"""
    <b>Address:</b> {address}<br>
    <b>Ward ID:</b> {ward_info['WardNo']}<br>
    <b>Councillor:</b> {ward_info['surname']}<br>
    <b>Attendance:</b> {ward_info['attendance_percentage']}%<br>
    <b>Party:</b> {ward_info['POLITICAL PARTY']}
    """

    folium.Marker(
        location=[location.latitude, location.longitude],
        popup=folium.Popup(popup_text, max_width=300),
        icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(map_object)

    print(f"✅ Address '{address}' added to the map!")

# ✅ Example Address for Testing
add_address_marker("28 Inanda", m)
m.get_root().html.add_child(folium.Element(search_html))

# ✅ Save the Map as an HTML File
m.save("interactive_choropleth.html")
m
print("✅ Map saved! Share 'interactive_choropleth.html' with your team.")

#%%
m.get_root().html.add_child(folium.Element(legend_html))

# Display the map
m.save("my_rep_interactive_choropleth.html")
m
#%%
# 1️⃣ Party Representation
party_counts = complete_gdf["POLITICAL PARTY"].value_counts().reset_index()
party_counts.columns = ["POLITICAL PARTY", "Count"]
fig1 = px.bar(party_counts, x="POLITICAL PARTY", y="Count", title="Councillor Representation by Party", color="POLITICAL PARTY")

# 2️⃣ Bottom 5 Councillors by Attendance
bottom_5 = complete_gdf.nsmallest(5, "attendance_percentage")[["surname", "POLITICAL PARTY", "attendance_percentage"]]
fig2 = px.bar(bottom_5, x="surname", y="attendance_percentage", orientation="v", 
              title="Bottom 5 Councillors by Attendance", color="attendance_percentage")

# 3️⃣ Average Attendance by Party
attendance_by_party = complete_gdf.groupby("POLITICAL PARTY")["attendance_percentage"].mean().reset_index()
fig3 = px.bar(attendance_by_party, y="attendance_percentage", x="POLITICAL PARTY", orientation="v",
              title="Avg Attendance by Party", color="attendance_percentage")

# Convert Plotly figures to HTML
chart1_html = fig1.to_html(full_html=False, include_plotlyjs="cdn")
chart2_html = fig2.to_html(full_html=False, include_plotlyjs=False)
chart3_html = fig3.to_html(full_html=False, include_plotlyjs=False)

# Create an HTML container for the charts
charts_html = f"""
<div style="position: fixed; top: 100px; right: 10px; width: 480px; background: white; padding: 10px; 
            border-radius: 5px; box-shadow: 2px 2px 5px grey; z-index: 1000; overflow-y: scroll; max-height: 600px;">
    <h4>📊 Insights</h4>
    {chart1_html}
    {chart2_html}
    {chart3_html}
</div>
"""

# Add the panel to the map
m.get_root().html.add_child(folium.Element(charts_html))

# Save & Display the Map
m.save("interactive_choropleth.html")
print("✅ Map saved! Open 'interactive_choropleth.html'")

#%%
complete_gdf = complete_gdf.set_geometry("geometry")

complete_gdf.to_file(r'c:\users\thandi\documents\github\my representative\myrep_attendance_analysis\annual_attendance.geojson', driver="GeoJSON", engine="fiona")
