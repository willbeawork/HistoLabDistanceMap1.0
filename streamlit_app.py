import numpy as np
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from pyproj import Transformer
import os

st.set_page_config(page_title="Closest Lab Finder", page_icon="🔬", layout="centered")

st.title("🔬 Closest Histology Lab Finder")
st.markdown("Enter a postcode to find the nearest histology labs.")

# --- Coordinate converter: British National Grid -> Lat/Lon ---
transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

def to_latlon(easting, northing):
    lon, lat = transformer.transform(easting, northing)
    return lat, lon

# --- Load data ---
postcode_gridref_df = pd.read_csv("ExtraReducedPostcodes.csv")
postcode_gridref_df.columns = postcode_gridref_df.columns.str.strip()

labs_df = pd.read_csv("nhs_histopath_labs_full.csv")
labs_df.columns = labs_df.columns.str.strip()


# --- Core function ---
def find_closest_labs(postcode, labs_df, postcode_df, n=2):
    postcode = postcode.strip().upper()
    match = postcode_df[postcode_df['PCDS'].str.strip().str.upper() == postcode]

    if match.empty:
        return None, None, f"Postcode '{postcode}' not found in database."

    postcode_row = match.iloc[0]

    distances = np.sqrt(
        (labs_df['OSEAST100M'] - postcode_row['OSEAST100M'])**2 +
        (labs_df['OSNRTH100M'] - postcode_row['OSNRTH100M'])**2
    )

    result = labs_df.copy()
    result['distance_m'] = distances
    result['distance_km'] = (result['distance_m'] / 1000).round(1)
    result = result.sort_values('distance_m').head(n)
    result['Postcode'] = postcode

    return result[['Postcode', 'Lab Name', 'distance_km', 'OSEAST100M', 'OSNRTH100M', 'Email Address']], postcode_row, None

st.session_state.setdefault('result', None)
st.session_state.setdefault('postcode_row', None)
st.session_state.setdefault('searched_postcode', None)

# --- UI ---
col1, col2 = st.columns([2, 1])

with col1:
    postcode_input = st.text_input("Postcode", placeholder="e.g. SW1A 1AA")
with col2:
    n_labs = st.number_input("Number of labs", min_value=1, max_value=10, value=2)

if st.button("Find Closest Labs", type="primary"):
    if not postcode_input.strip():
        st.warning("Please enter a postcode.")
    else:
        with st.spinner("Searching..."):
            result, postcode_row, error = find_closest_labs(postcode_input, labs_df, postcode_gridref_df, n=n_labs)

        if error:
            st.error(error)
            st.session_state.result = None
        else:
            # Save to session state so results persist across reruns
            st.session_state.result = result
            st.session_state.postcode_row = postcode_row
            st.session_state.searched_postcode = postcode_input.strip().upper()

# --- Display results (from session state) ---
if st.session_state.result is not None:
    result = st.session_state.result
    postcode_row = st.session_state.postcode_row

    st.success(f"Found {len(result)} closest lab(s) to **{st.session_state.searched_postcode}**")

    st.dataframe(
        result[['distance_km', 'Lab Name', 'Email Address']].rename(columns={"distance_km": "Distance (km)"}),
        use_container_width=True,
        hide_index=True
    )

# --- Map ---
    def to_latlon(easting, northing):
        lon, lat = transformer.transform(easting * 100, northing * 100)
        return lat, lon
    
    user_lat, user_lon = to_latlon(postcode_row['OSEAST100M'], postcode_row['OSNRTH100M'])

    m = folium.Map(location=[user_lat, user_lon], zoom_start=9, tiles="CartoDB positron")

    # User postcode pin (blue)
    folium.Marker(
        location=[user_lat, user_lon],
        popup=folium.Popup(f"<b>Your postcode</b><br>{st.session_state.searched_postcode}", max_width=200),
        tooltip="Your postcode",
        icon=folium.Icon(color="blue", icon="map-marker", prefix="fa")
    ).add_to(m)

    # Lab pins (red)
    for _, row in result.iterrows():
        lab_lat, lab_lon = to_latlon(row['OSEAST100M'], row['OSNRTH100M'])
        folium.Marker(
            location=[lab_lat, lab_lon],
            popup=folium.Popup(f"<b>{row['Lab Name']}</b><br>{row['distance_km']} km away", max_width=200),
            tooltip=row['Lab Name'],
            icon=folium.Icon(color="red", icon="flask", prefix="fa")
        ).add_to(m)

    st_folium(m, use_container_width=True, height=450)
