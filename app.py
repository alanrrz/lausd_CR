import streamlit as st
import pandas as pd
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from shapely.geometry import Point, shape
import usaddress

# --- REGION FILES ---
REGION_URLS = {
    "CENTRAL": "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/b0d5501614753fa530532c2f55a48eea4bed7607/C.csv",
    "EAST": "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/b0d5501614753fa530532c2f55a48eea4bed7607/E.csv",
    "NORTHEAST": "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/b0d5501614753fa530532c2f55a48eea4bed7607/NE.csv",
    "NORTHWEST": "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/947adbaa5bb342fb18725b6f4ade655a83eb2111/NW.csv",
    "SOUTH": "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/b0d5501614753fa530532c2f55a48eea4bed7607/S.csv",
    "WEST": "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/d6d9a1384a8a677bdf135b49ddd6540cdfc02cbc/W.csv"
}
SCHOOLS_URL = "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/ab73deb13c0a02107f43001161ab70891630a9c7/schools.csv"

@st.cache_data
def load_schools():
    return pd.read_csv(SCHOOLS_URL)

@st.cache_data
def load_addresses(url):
    return pd.read_csv(url)

def parse_address(line):
    try:
        parsed, _ = usaddress.tag(line)
        return {
            "House Number": parsed.get("AddressNumber", ""),
            "Street": " ".join([
                parsed.get("StreetNamePreDirectional", ""),
                parsed.get("StreetName", ""),
                parsed.get("StreetNamePostType", ""),
                parsed.get("StreetNamePostDirectional", ""),
            ]).strip(),
            "City": parsed.get("PlaceName", ""),
            "State": parsed.get("StateName", ""),
            "ZIP": parsed.get("ZipCode", ""),
            "Original": line
        }
    except usaddress.RepeatedLabelError:
        return {
            "House Number": "",
            "Street": "",
            "City": "",
            "State": "",
            "ZIP": "",
            "Original": line
        }

st.title("📍 School Community Address Finder & Parser")
st.caption(
    "Draw a circle, rectangle, or polygon on the map to select addresses. "
    "Filtered addresses will be parsed into components and available for download. "
    "Parsed results appear above the map."
)

schools = load_schools()
schools.columns = schools.columns.str.strip()
site_list = schools["LABEL"].sort_values().tolist()
site_selected = st.selectbox("Select Campus", site_list)

# container to show results *above the map*
result_container = st.container()

if site_selected:
    selected_school_row = schools[schools["LABEL"] == site_selected].iloc[0]
    school_region = selected_school_row["SHORTNAME"].upper()
    slon, slat = selected_school_row["LON"], selected_school_row["LAT"]

    if school_region not in REGION_URLS:
        st.error(f"No addresses file found for region: {school_region}")
        st.stop()

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
            'circle': True,
            'polygon': True,
            'marker': False,
            'circlemarker': False,
        },
        edit_options={'edit': True}
    )
    draw.add_to(fmap)

    st.write("**Draw one or more shapes on the map. Circles, rectangles, and polygons are supported.**")
    map_data = st_folium(fmap, width=700, height=500)

    features = []
    if map_data and "all_drawings" in map_data and map_data["all_drawings"]:
        features = map_data["all_drawings"]
    elif map_data and "last_active_drawing" in map_data and map_data["last_active_drawing"]:
        features = [map_data["last_active_drawing"]]

    if st.button("Filter & Parse Addresses"):
        if not features or len(features) == 0:
            result_container.warning("Please draw at least one shape.")
            st.stop()

        polygons = []

        for feature in features:
            try:
                geojson_geom = feature["geometry"]
                if geojson_geom["type"] == "Polygon":
                    polygons.append(shape(geojson_geom))
                elif geojson_geom["type"] == "Point" and "radius" in feature:
                    center = Point(geojson_geom["coordinates"])
                    radius_m = feature["radius"]
                    radius_deg = radius_m / 111_320
                    circle = center.buffer(radius_deg)
                    polygons.append(circle)
            except Exception as e:
                result_container.error(f"Could not interpret a drawn shape: {e}")

        if not polygons:
            result_container.error("No valid shapes drawn.")
            st.stop()

        def point_in_polygons(row):
            pt = Point(row["LON"], row["LAT"])
            return any(poly.contains(pt) or poly.touches(pt) for poly in polygons)

        filtered = addresses[addresses.apply(point_in_polygons, axis=1)]

        if filtered.empty:
            result_container.info("No addresses found within the drawn area(s).")
        else:
            parsed_rows = [parse_address(addr) for addr in filtered["FullAddress"].tolist()]
            parsed_df = pd.DataFrame(parsed_rows)

            with result_container:
                st.markdown(f"### 📝 Parsed Addresses Preview ({len(filtered)} addresses)")
                st.dataframe(parsed_df.head())

                csv = parsed_df.to_csv(index=False).encode("utf-8")

                st.download_button(
                    label=f"Download Parsed Addresses ({site_selected}_parsed.csv)",
                    data=csv,
                    file_name=f"{site_selected.replace(' ', '_')}_parsed.csv",
                    mime='text/csv'
                )
