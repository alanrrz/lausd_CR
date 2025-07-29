import streamlit as st
import pandas as pd
import folium
from folium.plugins import Draw, MeasureControl
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

def parse_address_expanded(line):
    try:
        parsed, _ = usaddress.tag(line)
        house_num = parsed.get("AddressNumber", "")
        street = " ".join([
            parsed.get("StreetNamePreDirectional", ""),
            parsed.get("StreetName", ""),
            parsed.get("StreetNamePostType", ""),
            parsed.get("StreetNamePostDirectional", ""),
        ]).strip()
        full_address = f"{house_num} {street}".strip()
        unit = parsed.get("OccupancyIdentifier", "")
        city = parsed.get("PlaceName", "")
        state = parsed.get("StateName", "")
        zip_code = parsed.get("ZipCode", "")

        rows = []
        # expand unit if it's a range
        if unit and "-" in unit:
            parts = unit.replace("–", "-").split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                start = int(parts[0])
                end = int(parts[1])
                for u in range(start, end + 1):
                    rows.append({
                        "Address": full_address,
                        "Unit": str(u),
                        "City": city,
                        "State": state,
                        "ZIP": zip_code,
                        "Original": line
                    })
                return rows
        # fallback — single row
        return [{
            "Address": full_address,
            "Unit": unit,
            "City": city,
            "State": state,
            "ZIP": zip_code,
            "Original": line
        }]
    except usaddress.RepeatedLabelError:
        return [{
            "Address": "",
            "Unit": "",
            "City": "",
            "State": "",
            "ZIP": "",
            "Original": line
        }]

st.title("📍 School Community Address Finder")
st.caption(
    "Find addresses near your selected school site for stakeholder notification and community engagement. "
    "Draw rectangles or polygons on the map to select exactly the blocks or areas you want included. "
    "You can also measure distances (in miles) to get a sense of scale. "
    "Only addresses inside your drawn shapes will be exported for download."
)

schools = load_schools()
schools.columns = schools.columns.str.strip()
site_list = schools["LABEL"].sort_values().tolist()
site_selected = st.selectbox("Select Campus", site_list)

result_container = st.container()

if site_selected:
    selected_school_row = schools[schools["LABEL"] == site_selected].iloc[0]
    school_region = selected_school_row["SHORTNAME"].upper()
    slon, slat = selected_school_row["LON"], selected_school_row["LAT"]

    if school_region not in REGION_URLS:
        st.error(f"No address file found for region: {school_region}")
        st.stop()

    addresses = load_addresses(REGION_URLS[school_region])
    addresses.columns = addresses.columns.str.strip()
    addresses["LAT"] = pd.to_numeric(addresses["LAT"], errors="coerce")
    addresses["LON"] = pd.to_numeric(addresses["LON"], errors="coerce")

    fmap = folium.Map(location=[slat, slon], zoom_start=15)
    folium.Marker([slat, slon], tooltip=site_selected, icon=folium.Icon(color="blue")).add_to(fmap)

    # Draw shapes
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
        edit_options={
            'edit': True,
            'remove': True,
        }
    )
    draw.add_to(fmap)

    # Add measuring tool in miles
    fmap.add_child(MeasureControl(primary_length_unit='miles'))

    st.info("📐 Tip: After drawing your shape, click the starting point or double‑click to finish. Use the trash icon to delete and redraw if needed.")

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
            all_rows = []
            for addr in filtered["FullAddress"].tolist():
                all_rows.extend(parse_address_expanded(addr))

            parsed_df = pd.DataFrame(all_rows)

            with result_container:
                st.markdown(f"### 📝 Parsed Addresses Preview ({len(parsed_df)} rows)")
                st.dataframe(parsed_df.head())

                csv = parsed_df.to_csv(index=False).encode("utf-8")

                st.download_button(
                    label=f"Download Parsed Addresses ({site_selected}_parsed.csv)",
                    data=csv,
                    file_name=f"{site_selected.replace(' ', '_')}_parsed.csv",
                    mime='text/csv'
                )
