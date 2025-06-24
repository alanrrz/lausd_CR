import streamlit as st
import pandas as pd
import numpy as np
import math
import folium
from streamlit_folium import st_folium
from pyproj import Transformer
import requests
import os

# --- Download Data from Dropbox (once per session) ---
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

# --- Haversine distance function ---
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

# --- Streamlit UI ---
st.title("LAUSD School Buffer Address Finder")

school_list = schools["label"].sort_values().tolist()
school_selected = st.selectbox("Select School", school_list)
radius_selected = st.select_slider("Radius (miles)", options=[round(x/10,1) for x in range(1,7)] + list(range(1,6)), value=0.5)

if st.button("Preview Map"):
    row = schools[schools["label"] == school_selected].iloc[0]
    slon, slat = row["lon"], row["lat"]
    radius = radius_selected

    # Calculate distances and filter
    addresses["distance"] = addresses.apply(
        lambda r: haversine(slon, slat, r["lon"], r["lat"]), axis=1
    )
    within = addresses[addresses["distance"] <= radius]

    # Build map
    fmap = folium.Map(location=[slat, slon], zoom_start=15)
    folium.Marker([slat, slon], tooltip=school_selected, icon=folium.Icon(color="blue")).add_to(fmap)
    folium.Circle([slat, slon], radius=radius*1609.34, color='red', fill=True, fill_opacity=0.1).add_to(fmap)
    for _, row2 in within.head(200).iterrows():
        folium.CircleMarker([row2["lat"], row2["lon"]], radius=2, color='green').add_to(fmap)

    st.write(f"**Preview:** {len(within)} addresses found within {radius} miles. (First 200 shown on map)")
    st_folium(fmap, width=700, height=500)

    # Option to download
    csv = within[["address","lon","lat","distance"]].to_csv(index=False)
    st.download_button(
        label=f"Download CSV ({school_selected}_{radius}mi.csv)",
        data=csv,
        file_name=f"{school_selected.replace(' ', '_')}_{radius}mi.csv",
        mime='text/csv'
    )
else:
    st.info("Select school and radius, then click 'Preview Map'.")

