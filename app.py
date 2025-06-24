import streamlit as st
import pandas as pd
import numpy as np
import math
import folium
from streamlit_folium import st_folium
from pyproj import Transformer
import requests
import os

@st.cache_data
def download_and_load():
    dropbox_urls = {
        "addresses.csv": "https://www.dropbox.com/scl/fi/ika7darb79t1zbuzjpj90/addresses.csv?rlkey=h8anuof8jc4n70ynsrwd9svue&st=7rbiczlv&dl=1",
        "schools.csv": "https://www.dropbox.com/scl/fi/qt5wmh9raabpjjykuvslt/schools.csv?rlkey=m7xtw0790sfv9djxz62h2ypzk&st=9aho2onv&dl=1"
    }
    for fname, url in dropbox_urls.items():
        if not os.path.isfile(fname):
            r = requests.get(url)
            with open(fname, "wb") as f:
                f.write(r.content)
    schools = pd.read_csv("schools.csv", sep=",")
    addresses = pd.read_csv("addresses.csv", sep=";")
    return schools, addresses

schools, addresses = download_and_load()

# --- Coordinate conversion ---
tr_addr = Transformer.from_crs("EPSG:2229", "EPSG:4326", always_xy=True)
addresses[["lon", "lat"]] = np.array(tr_addr.transform(addresses["lon"].values, addresses["lat"].values)).T

tr_sch = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
schools[["lon", "lat"]] = np.array(tr_sch.transform(schools["lon"].values, schools["lat"].values)).T

def haversine(lon1, lat1, lon2, lat2):
    R = 3959  # miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat/2)**2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon/2)**2
    )
    return 2 * R * math.asin(math.sqrt(a))

st.title("LAUSD Campus Buffer Address Finder")

site_list = schools["label"].sort_values().tolist()
site_selected = st.selectbox("Select Campus", site_list)
radius_selected = st.select_slider(
    "Radius (miles)",
    options=[round(x/10,1) for x in range(1,7)] + list(range(1,6)),
    value=0.5
)

if "show_map" not in st.session_state:
    st.session_state["show_map"] = False
if "csv_ready" not in st.session_state:
    st.session_state["csv_ready"] = False

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("Preview Map"):
        st.session_state["show_map"] = True
        st.session_state["csv_ready"] = True
with col2:
    if st.button("Reset"):
        st.session_state["show_map"] = False
        st.session_state["csv_ready"] = False

if st.session_state["show_map"]:
    row = schools[schools["label"] == site_selected].iloc[0]
    slon, slat = row["lon"], row["lat"]
    radius = radius_selected

    # CSV generation for addresses in buffer
    addresses["distance"] = addresses.apply(
        lambda r: haversine(slon, slat, r["lon"], r["lat"]), axis=1
    )
    within = addresses[addresses["distance"] <= radius]
    csv = within[["address","lon","lat","distance"]].to_csv(index=False)

    # Download button (always above map)
    st.download_button(
        label=f"Download CSV ({site_selected}_{radius}mi.csv)",
        data=csv,
        file_name=f"{site_selected.replace(' ', '_')}_{radius}mi.csv",
        mime='text/csv'
    )

    # Map (just marker and buffer)
    fmap = folium.Map(location=[slat, slon], zoom_start=15)
    folium.Marker([slat, slon], tooltip=site_selected, icon=folium.Icon(color="blue")).add_to(fmap)
    folium.Circle([slat, slon], radius=radius*1609.34, color='red', fill=True, fill_opacity=0.1).add_to(fmap)

    st.write(f"**Preview:** Buffer around {site_selected} ({radius} miles). If this looks correct, use the button above to download.")
    st_folium(fmap, width=700, height=500)
else:
    st.info("Select campus and radius, then click 'Preview Map'.")

