import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Capacity Planner", layout="wide")

def load_and_clean_data(uploaded_file):
    df = pd.read_csv(uploaded_file)
    
    # Clean headers
    df.columns = df.columns.str.strip()
    
    # --- DIAGNOSTIC LOG (Visible in App) ---
    with st.expander("🔍 Data Diagnostic - Click to see why Locales might be missing"):
        st.write("First 5 rows of raw data (Top Headers):")
        st.dataframe(df.head())
        st.write("Detected Columns:", list(df.columns))

    new_df = pd.DataFrame()
    
    try:
        # 1. FORCE ASSIGNMENT BY POSITION (Based on your screenshot)
        # We use .iloc to ensure we grab the right physical column
        new_df["site"] = df.iloc[:, 0].astype(str).str.strip()
        new_df["locale"] = df.iloc[:, 1].astype(str).str.strip()
        
        # Column-4 is index 3
        new_df["workflow"] = df.iloc[:, 3].astype(str).str.strip()
        
        # Units and AHT (Adjusting indices to match the screenshot better)
        # If 'Processed' is Column 13 and 'AHT' is Column 15:
        proc_idx = [i for i, c in enumerate(df.columns) if "Processed" in c]
        new_df["units"] = df.iloc[:, proc_idx[0]] if proc_cols else df.iloc[:, 13]
        
        aht_idx = [i for i, c in enumerate(df.columns) if "Average Handle Time" in c]
        new_df["aht"] = df.iloc[:, aht_idx[0]] if aht_cols else df.iloc[:, 15]
        
    except Exception as e:
        st.error(f"Mapping Error: {e}")
        return pd.DataFrame()

    # 2. STRING CLEANING (Crucial for en_uk/CBG visibility)
    # We remove 'nan' strings that occur when cells are empty
    for col in ["site", "workflow", "locale"]:
        new_df = new_df[new_df[col].notna()]
        new_df = new_df[new_df[col].str.lower() != "nan"]
        new_df = new_df[new_df[col] != ""]

    # 3. NUMERIC CONVERSION
    new_df["aht"] = pd.to_numeric(new_df["aht"], errors="coerce").fillna(0)
    new_df["units"] = pd.to_numeric(new_df["units"], errors="coerce").fillna(0)
    
    return new_df

# --- MAIN UI ---
st.title("📊 Weekly Capacity Planner")

uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type=["csv"])

if uploaded_file:
    df = load_and_clean_data(uploaded_file)
    
    if not df.empty:
        # SIDEBAR CONFIG
        st.sidebar.divider()
        qas_per_site = st.sidebar.number_input("Target QAs per Locale", min_value=1, value=10)
        prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
        growth_per_week = st.sidebar.slider("Weekly Growth (%)", 0, 20, 5)

        # --- THE SITE/LOCALE ASSIGNMENT LOGIC ---
        all_sites = sorted(df['site'].unique())
        selected_sites = st.sidebar.multiselect("1. Select Sites:", all_sites, default=all_sites)
        
        # We filter the dataframe FIRST by site to find valid locales
        site_filtered_df = df[df['site'].isin(selected_sites)]
        relevant_locs = sorted(site_filtered_df['locale'].unique())
        
        # Select Locales
        selected_locales = st.sidebar.multiselect("2. Select Locales:", relevant_locs, default=relevant_locs)
        
        # Final DataFrame for calculation
        f_df = site_filtered_df[site_filtered_df['locale'].isin(selected_locales)]

        if f_df.empty:
            st.warning("No data matches the current selection.")
        else:
            tab1, tab2 = st.tabs(["📊 Historical", "🚀 Prediction"])

            with tab1:
                st.subheader("Workflow Breakdown")
                summary = f_df.groupby(['locale', 'workflow']).agg({'units': 'sum', 'aht': 'mean'}).reset_index()
                st.dataframe(summary, use_container_width=True)

            with tab2:
                # Prediction Logic
                monday = (datetime.now() + timedelta(days=(0-datetime.now().weekday()) % 7))
                if monday <= datetime.now(): monday += timedelta(days=7)
                
                week_opts = [f"Week {i}: {(monday + timedelta(weeks=i-1)).strftime('%d %b')}" for i in range(1, 5)]
                selected_week = st.selectbox("Select Week:", week_opts)
                w_idx = int(selected_week.split(":")[0].split(" ")[1])

                res = []
                for (loc, wf), group in f_df.groupby(['locale', 'workflow']):
                    vol = (group['units'].sum() / 11) * ((1 + (growth_per_week/100))**w_idx)
                    aht_val = group['aht'].mean()
                    hrs = (vol * aht_val) / 3600 if aht_val > 0 else 0
                    hc = hrs / (prod_hours * 5) if prod_hours > 0 else 0
                    
                    wf_count = len(f_df[f_df['locale'] == loc]['workflow'].unique())
                    res.append({
                        "Locale": loc,
                        "Transformation Type": wf,
                        "Exp. Vol": int(vol),
                        "HC Needed": hc,
                        "Surplus/Deficit": (qas_per_site / wf_count) - hc
                    })
                
                st.dataframe(pd.DataFrame(res), use_container_width=True)
    else:
        st.error("Data failed to load. Check the Diagnostic expander above.")

else:
    st.info("Upload CSV to begin.")
