import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from shapely.geometry import Point, shape

# --- REGION FILES ---
REGION_URLS = {
    "CENTRAL": "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/b0d5501614753fa530532c2f55a48eea4bed7607/C.csv",
    "EAST": "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/b0d5501614753fa530532c2f55a48eea4bed7607/E.csv",
    "NORTHEAST": "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/b0d5501614753fa530532c2f55a48eea4bed7607/NE.csv",
    "NORTHWEST": "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/b0d5501614753fa530532c2f55a48eea4bed7607/NW.csv",
    "SOUTH": "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/b0d5501614753fa530532c2f55a48eea4bed7607/S.csv",
    "WEST": "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/d6d9a1384a8a677bdf135b49ddd6540cdfc02cbc/W.csv"
}
SCHOOLS_URL = "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/ab73deb13c0a02107f43001161ab70891630a9c7/schools.csv"

@st.cache_data
def load_schools():
    return pd.read_csv(SCHOOLS_URL)

st.title("Draw Custom Blocks: School Community Address Finder")
st.caption("Draw rectangles or polygons to select which blocks/areas you want to notify. Only addresses inside your shapes will be exported.")

schools = load_schools()
schools.columns = schools.columns.str.strip()
site_list = schools["LABEL"].sort_values().tolist()
site_selected = st.selectbox("Select Campus", site_list)

if site_selected:
    selected_school_row = schools[schools["LABEL"] == site_selected].iloc[0]
    school_region = selected_school_row["SHORTNAME"].upper()
    slon, slat = selected_school_row["LON"], selected_school_row["LAT"]

    if school_region not in REGION_URLS:
        st.error(f"No addresses file found for region: {school_region}")
        st.stop()

    @st.cache_data
    def load_addresses(url):
        return pd.read_csv(url)

    addresses = load_addresses(REGION_URLS[school_region])
    addresses.columns = addresses.columns.str.strip()
    addresses["LAT"] = pd.to_numeric(addresses["LAT"], errors="coerce")
    addresses["LON"] = pd.to_numeric(addresses["LON"], errors="coerce")

    fmap = folium.Map(location=[slat, slon], zoom_start=15)
    folium.Marker([slat, slon], tooltip=site_selected, icon=folium.Icon(color="blue")).add_to(fmap)

    draw = Draw(
        export=True,
        filename='drawn.geojson',
        position='topleft',
        draw_options={
            'polyline': False,
            'rectangle': True,
            'circle': False,
            'polygon': True,
            'marker': False,
            'circlemarker': False,
        },
        edit_options={'edit': True}
    )
    draw.add_to(fmap)

    st.write("**Draw one or more rectangles or polygons on the map. Overlap is allowed.**")
    map_data = st_folium(fmap, width=700, height=500)

    features = []
    if map_data and "all_drawings" in map_data and map_data["all_drawings"]:
        features = map_data["all_drawings"]
    elif map_data and "last_active_drawing" in map_data and map_data["last_active_drawing"]:
        features = [map_data["last_active_drawing"]]

    if st.button("Filter Addresses in Drawn Area(s)"):
        st.write(f"Features drawn: {len(features)}" if features else "Features drawn: 0")
        if not features or len(features) == 0:
            st.warning("Please draw at least one rectangle or polygon to select blocks.")
        else:
            polygons = []
            for feature in features:
                try:
                    geojson_geom = feature["geometry"]
                    shapely_geom = shape(geojson_geom)
                    polygons.append(shapely_geom)
                except Exception as e:
                    st.error(f"Could not interpret a drawn shape: {e}")

            if not polygons:
                st.error("No valid polygons drawn.")
                st.stop()

            # For each address, check if it's in ANY polygon
            def point_in_polygons(row):
                pt = Point(row["LON"], row["LAT"])
                return any(poly.contains(pt) or poly.touches(pt) for poly in polygons)

            filtered = addresses[addresses.apply(point_in_polygons, axis=1)]

            st.write(f"Filtered addresses count: {len(filtered)}")
            if not filtered.empty:
                st.write("Preview of addresses found in area:")
                st.write(filtered[["FullAddress"]].head(5))  # Show a sample
                csv = filtered[["FullAddress"]].rename(columns={"FullAddress": "Address"}).to_csv(index=False)
                st.download_button(
                    label=f"Download Addresses ({site_selected}_custom_blocks.csv)",
                    data=csv,
                    file_name=f"{site_selected.replace(' ', '_')}_custom_blocks.csv",
                    mime='text/csv'
                )
            else:
                st.info("No addresses found within the drawn area(s).")

else:
    st.info("Select a campus above to begin.")
