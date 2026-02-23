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
POSTCODE_FILE = "postcodes_short.csv"
LABS_FILE = "Histo labs example.csv"

@st.cache_data
def load_from_disk():
    postcode_gridref_df = pd.read_csv(POSTCODE_FILE)
    df_labs = pd.read_csv(LABS_FILE)
    return postcode_gridref_df, df_labs

@st.cache_data
def load_from_uploads(postcode_file, labs_file):
    postcode_gridref_df = pd.read_csv(postcode_file)
    df_labs = pd.read_csv(labs_file)
    return postcode_gridref_df, df_labs

files_on_disk = os.path.exists(POSTCODE_FILE) and os.path.exists(LABS_FILE)

if files_on_disk:
    postcode_gridref_df, df_labs = load_from_disk()
else:
    st.info("Default data files not found. Please upload them below.")
    with st.expander("📂 Upload data files", expanded=True):
        postcode_file = st.file_uploader("Postcode grid reference CSV", type="csv",
                                          help="Columns needed: Postcode, Easting Grid Ref, Northing Grid Ref")
        labs_file = st.file_uploader("Histology labs CSV", type="csv",
                                      help="Columns needed: Lab, Easting, Northing")
    if postcode_file is None or labs_file is None:
        st.stop()
    postcode_gridref_df, df_labs = load_from_uploads(postcode_file, labs_file)

# --- Core function ---
def find_closest_labs(postcode, labs_df, postcode_df, n=2):
    postcode = postcode.strip().upper()
    match = postcode_df[postcode_df['Postcode'].str.strip().str.upper() == postcode]

    if match.empty:
        return None, None, f"Postcode '{postcode}' not found in database."

    postcode_row = match.iloc[0]

    distances = np.sqrt(
        (labs_df['Easting'] - postcode_row['Easting Grid Ref'])**2 +
        (labs_df['Northing'] - postcode_row['Northing Grid Ref'])**2
    )

    result = labs_df.copy()
    result['distance_m'] = distances
    result['distance_km'] = (result['distance_m'] / 1000).round(1)
    result = result.sort_values('distance_m').head(n)
    result['Postcode'] = postcode

    return result[['Postcode', 'Lab', 'distance_km', 'Easting', 'Northing']], postcode_row, None

# --- UI ---
col1, col2 = st.columns([2, 1])

with col1:
    postcode_input = st.text_input("Postcode", placeholder="e.g. EX5 2HD")
with col2:
    n_labs = st.number_input("Number of labs", min_value=1, max_value=10, value=2)

if st.button("Find Closest Labs", type="primary"):
    if not postcode_input.strip():
        st.warning("Please enter a postcode.")
    else:
        with st.spinner("Searching..."):
            result, postcode_row, error = find_closest_labs(postcode_input, df_labs, postcode_gridref_df, n=n_labs)

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
        result[['Postcode', 'Lab', 'distance_km']].rename(columns={"distance_km": "Distance (km)"}),
        use_container_width=True,
        hide_index=True
    )

 # --- Map ---
    user_lat, user_lon = to_latlon(postcode_row['Easting Grid Ref'], postcode_row['Northing Grid Ref'])

    m = folium.Map(location=[user_lat, user_lon], zoom_start=9, tiles="CartoDB positron")

    # User postcode pin (blue)
    folium.Marker(
        location=[user_lat, user_lon],
        popup=folium.Popup(f"<b>Your postcode</b><br>{st.session_state.searched_postcode}", max_width=200),
        tooltip="Your postcode",
        icon=folium.Icon(color="blue", icon="home", prefix="fa")
    ).add_to(m)

    # Lab pins (red)
    for _, row in result.iterrows():
        lab_lat, lab_lon = to_latlon(row['Easting'], row['Northing'])
        folium.Marker(
            location=[lab_lat, lab_lon],
            popup=folium.Popup(f"<b>{row['Lab']}</b><br>{row['distance_km']} km away", max_width=200),
            tooltip=row['Lab'],
            icon=folium.Icon(color="red", icon="flask", prefix="fa")
        ).add_to(m)

        # Dashed line from postcode to lab
        folium.PolyLine(
            locations=[[user_lat, user_lon], [lab_lat, lab_lon]],
            color="gray",
            weight=1.5,
            dash_array="6"
        ).add_to(m)

    st_folium(m, use_container_width=True, height=450)
