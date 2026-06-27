#import required librarys
import numpy as np
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from pyproj import Transformer
import os

#Messy Phleb Grid Ref Adustment
phlebotomydf = pd.read_csv("FakePhlebDatabase.csv")
phlebotomydf["OSEAST100M"]=phlebotomydf["OSEAST100M"]/100
phlebotomydf["OSNRTH100M"]=phlebotomydf["OSNRTH100M"]/100

# --- Page config ---
st.set_page_config(page_title="Find that lab for genetics clinicians", layout="wide")
st.title("Find that lab for genetics clinicians")
st.write("Developed for use by cancer genetics clinicians")

# --- Session state initialisation (ALWAYS FIRST) ---
if "selected_option" not in st.session_state:
    st.session_state.selected_option = "Histology Lab Finder"
if "result" not in st.session_state:
    st.session_state.result = None
if "postcode_row" not in st.session_state:
    st.session_state.postcode_row = None
if "searched_postcode" not in st.session_state:
    st.session_state.searched_postcode = None

# --- Mode switcher ---
def select_option(option):
    # Clear results when switching mode
    st.session_state.result = None
    st.session_state.postcode_row = None
    st.session_state.searched_postcode = None
    st.session_state.selected_option = option

st.write(f"🔍 **Current Search Mode:** {st.session_state.selected_option}")

left, middle, right = st.columns(3)
with left:
    if st.button("*Histology Lab Finder*", width="stretch"):
        select_option("Histology Lab Finder")
with middle:
    if st.button("*Genetics Lab Finder*", width="stretch"):
        select_option("Genetics Lab Finder")
with right:
    if st.button("*Phlebotomy Clinic Finder*", width="stretch"):
        select_option("Phlebotomy Clinic Finder")

# --- Shared utilities ---
transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

def to_latlon(easting, northing):
    lon, lat = transformer.transform(easting * 100, northing * 100)
    return lat, lon

@st.cache_data
def load_postcodes():
    df = pd.read_csv("ExtraReducedPostcodes.autoshortened.csv")
    df.columns = df.columns.str.strip()
    return df

postcode_gridref_df = load_postcodes()

# --- Shared search function ---
def find_closest(postcode, labs_df, postcode_df, name_col, contact_cols, n=2):
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
    result['distance_m'] = distances * 100
    result['distance_km'] = (result['distance_m'] / 1000).round(1)
    result = result.sort_values('distance_m').head(n)
    result['Postcode'] = postcode

    cols_to_return = ['Postcode', name_col, 'distance_km', 'OSEAST100M', 'OSNRTH100M'] + contact_cols
    return result[cols_to_return], postcode_row, None

# --- Shared UI for search + results + map ---
def run_search_ui(labs_df, name_col, display_cols, n_default=2):
    """
    name_col: the column used for marker labels/popups (e.g. 'Lab Name', 'Phleb Name')
    display_cols: dict mapping {column_name_in_csv: display_label_for_table}
                  e.g. {"Fake Phone Number": "Phone", "Opening Hours": "Hours", "Address": "Address"}
    """
    labs_df = labs_df.copy()
    labs_df.columns = labs_df.columns.str.strip()

    col1, col2 = st.columns([2, 1])
    with col1:
        postcode_input = st.text_input("Postcode", placeholder="e.g. SW1A 1AA")
    with col2:
        n_results = st.number_input("Number of results", min_value=1, max_value=10, value=n_default)

    if st.button("Search", type="primary"):
        if not postcode_input.strip():
            st.warning("Please enter a postcode.")
        else:
            with st.spinner("Searching..."):
                result, postcode_row, error = find_closest(
                    postcode_input, labs_df, postcode_gridref_df,
                    name_col, list(display_cols.keys()), n=n_results
                )
            if error:
                st.error(error)
                st.session_state.result = None
            else:
                st.session_state.result = result
                st.session_state.postcode_row = postcode_row
                st.session_state.searched_postcode = postcode_input.strip().upper()

        # --- Map ---
        user_lat, user_lon = to_latlon(postcode_row['OSEAST100M'], postcode_row['OSNRTH100M'])
        m = folium.Map(location=[user_lat, user_lon], zoom_start=9, tiles="CartoDB positron")

        folium.Marker(
            location=[user_lat, user_lon],
            popup=folium.Popup(f"<b>Your postcode</b><br>{st.session_state.searched_postcode}", max_width=200),
            tooltip="Your postcode",
            icon=folium.Icon(color="blue", icon="map-marker", prefix="fa")
        ).add_to(m)

        for _, row in result.iterrows():
            lat, lon = to_latlon(row['OSEAST100M'], row['OSNRTH100M'])
            # Build popup with all display_cols, not just one
            popup_lines = [f"<b>{row[name_col]}</b>", f"{row['distance_km']} km away"]
            for col in display_cols:
                popup_lines.append(f"{display_cols[col]}: {row[col]}")
            popup_html = "<br>".join(popup_lines)

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=row[name_col],
                icon=folium.Icon(color="red", icon="flask", prefix="fa")
            ).add_to(m)

        st_folium(m, use_container_width=True, height=450)
    # --- Results ---
    if st.session_state.result is not None:
        result = st.session_state.result
        postcode_row = st.session_state.postcode_row

        st.success(f"Found {len(result)} result(s) closest to **{st.session_state.searched_postcode}**")

        table_cols = ['distance_km', name_col] + list(display_cols.keys())
        rename_map = {"distance_km": "Distance (km)", **display_cols}

        st.dataframe(
            result[table_cols].rename(columns=rename_map),
            use_container_width=True,
            hide_index=True
        )

        # --- Map ---
        user_lat, user_lon = to_latlon(postcode_row['OSEAST100M'], postcode_row['OSNRTH100M'])
        m = folium.Map(location=[user_lat, user_lon], zoom_start=9, tiles="CartoDB positron")

        folium.Marker(
            location=[user_lat, user_lon],
            popup=folium.Popup(f"<b>Your postcode</b><br>{st.session_state.searched_postcode}", max_width=200),
            tooltip="Your postcode",
            icon=folium.Icon(color="blue", icon="map-marker", prefix="fa")
        ).add_to(m)

        for _, row in result.iterrows():
            lat, lon = to_latlon(row['OSEAST100M'], row['OSNRTH100M'])
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(f"<b>{row[name_col]}</b><br>{row['distance_km']} km away", max_width=200),
                tooltip=row[name_col],
                icon=folium.Icon(color="red", icon="flask", prefix="fa")
            ).add_to(m)

        st_folium(m, use_container_width=True, height=450)

# --- Route to correct mode ---
st.subheader("Enter a postcode")

if st.session_state.selected_option == "Histology Lab Finder":
    histologydf = pd.read_csv("Fake_email_histo_lab_dataset.csv")
    run_search_ui(
        histologydf,
        name_col="Lab Name",
        display_cols={"Fake Email": "Email"}
    )

elif st.session_state.selected_option == "Genetics Lab Finder":
    st.info("Genetics Lab Finder coming soon.")

elif st.session_state.selected_option == "Phlebotomy Clinic Finder":
    run_search_ui(
    phlebotomydf,
    name_col="Phleb Name",
    display_cols={
        "Fake Phone Number": "Phone",
        "Opening Hours Details": "Opening Hours",
        "Address": "Address",
        "Additional Restrictions": "Additional Restrictions"
    }
)
