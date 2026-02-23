import numpy as np
import pandas as pd
import streamlit as st
import os

st.set_page_config(page_title="Closest Lab Finder", page_icon="🔬", layout="centered")

st.title("🔬 Closest Histology Lab Finder")
st.markdown("Enter a postcode to find the nearest histology labs.")

# --- Load data ---
# Try to load from disk first (pre-loaded in repo), fall back to file uploaders

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
def find_closest_labs(postcode, labs_df, postcode_df, n=2):
    """
    Find n closest labs to a postcode using Euclidean distance.
    Returns dataframe with closest labs and distances in km.
    """
    # Normalise postcode: uppercase and strip extra spaces
    postcode = postcode.strip().upper()

    # Try to find exact match first, then try normalised version
    match = postcode_df[postcode_df['Postcode'].str.strip().str.upper() == postcode]
    
    if match.empty:
        return None, f"Postcode '{postcode}' not found in database."

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

    return result[['Lab', 'Email', 'distance_km']], None

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
            result, error = find_closest_labs(postcode_input, df_labs, postcode_gridref_df, n=n_labs)

        if error:
            st.error(error)
        else:
            st.success(f"Found {len(result)} closest lab(s) to **{postcode_input.strip().upper()}**")
            st.dataframe(
                result.rename(columns={"distance_km": "Distance (km)"}),
                use_container_width=True,
                hide_index=True
            )
