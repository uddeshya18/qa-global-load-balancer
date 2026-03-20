import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Capacity Planner", layout="wide")

# ---------------------------------------------------------------------------
# DATA LOADING (FORCE POSITION LOGIC)
# ---------------------------------------------------------------------------
def load_and_clean_data(uploaded_file):
    # Load raw data
    df = pd.read_csv(uploaded_file)
    
    # Clean all headers of whitespace
    df.columns = df.columns.str.strip()
    
    new_df = pd.DataFrame()
    
    # --- POSITION-BASED EXTRACTION (The "Safety Net") ---
    # Col 0: Site (Column-1)
    # Col 1: Locale (Column-2)
    # Col 3: Transformation Type (Column-4)
    
    try:
        new_df["site"] = df.iloc[:, 0]    # Grabs whatever is in the 1st column
        new_df["locale"] = df.iloc[:, 1]  # Grabs whatever is in the 2nd column
        
        # Search for Workflow (Transformation Type)
        wf_col = [c for c in df.columns if "Transformation" in c]
        new_df["workflow"] = df[wf_col[0]] if wf_col else df.iloc[:, 3]
        
        # Search for Processed (Units)
        proc_cols = [c for c in df.columns if "Processed" in c]
        new_df["units"] = df[proc_cols[0]] if proc_cols else df.iloc[:, 13]
        
        # Search for AHT
        aht_cols = [c for c in df.columns if "Average Handle Time" in c]
        new_df["aht"] = df[aht_cols[0]] if aht_cols else df.iloc[:, 15]

    except Exception as e:
        st.error(f"Critical Mapping Error: {e}")
        st.stop()

    # --- STRING CLEANING LOGIC (From your Model) ---
    for col in ["site", "workflow", "locale"]:
        if col in new_df.columns:
            new_df[col] = new_df[col].astype(str).str.strip()
            # This is what restores 'en_uk' and 'CBG' if they were 'nan'
            new_df = new_df[new_df[col].notna() & (new_df[col] != "") & (new_df[col] != "nan")]
    
    # --- NUMERIC CONVERSION ---
    new_df["aht"] = pd.to_numeric(new_df["aht"], errors="coerce")
    new_df["units"] = pd.to_numeric(new_df["units"], errors="coerce")
    
    # Final drop of empty rows
    new_df = new_df.dropna(subset=["aht", "units"])
    
    return new_df

# ---------------------------------------------------------------------------
# MAIN UI
# ---------------------------------------------------------------------------
st.title("📊 Weekly Capacity Planner")

uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type=["csv"])

if uploaded_file:
    df = load_and_clean_data(uploaded_file)
    
    # Final check for visibility
    if df.empty:
        st.error("The data is empty after cleaning. Check if Processed/AHT columns have numbers.")
        st.stop()

    # Sidebar Settings
    st.sidebar.divider()
    qas_per_site = st.sidebar.number_input("Target QAs per Locale", min_value=1, value=10)
    prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
    growth_per_week = st.sidebar.slider("Weekly Growth (%)", 0, 20, 5)

    # -----------------------------------------------------------------------
    # SITE & LOCALE LOGIC (Your Specific Requirement)
    # -----------------------------------------------------------------------
    all_sites = sorted(df['site'].unique())
    selected_sites = st.sidebar.multiselect("Select Sites:", all_sites, default=all_sites)
    
    # Filter available locales based on the site selection
    relevant_locs = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
    selected_locales = st.sidebar.multiselect("Select Locales:", relevant_locs, default=relevant_locs)
    
    # Data filtering
    f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

    if f_df.empty:
        st.warning("No data matches the current Site/Locale selection.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Forecast Prediction"])

        with tab1:
            st.subheader("Historical Workflow Breakdown")
            # Aggregation by Locale AND Workflow
            summary = f_df.groupby(['locale', 'workflow']).agg({
                'units': 'sum', 
                'aht': 'mean'
            }).reset_index()
            summary['Avg Weekly Vol'] = (summary['units'] / 11).astype(int)
            st.dataframe(summary.style.format({'aht': '{:.1f}'}), use_container_width=True)

        with tab2:
            st.subheader("Future Capacity Forecast")
            
            # Date Selection
            monday = (datetime.now() + timedelta(days=(0-datetime.now().weekday()) % 7))
            if monday <= datetime.now(): monday += timedelta(days=7)
            
            week_opts = [f"Week {i}: {(monday + timedelta(weeks=i-1)).strftime('%d %b')}" for i in range(1, 5)]
            selected_week = st.selectbox("Select Week:", week_opts)
            w_idx = int(selected_week.split(":")[0].split(" ")[1])

            results = []
            for (loc, wf), group in f_df.groupby(['locale', 'workflow']):
                # Prediction Calculations
                vol = (group['units'].sum() / 11) * ((1 + (growth_per_week/100))**w_idx)
                aht_val = group['aht'].mean()
                hrs = (vol * aht_val) / 3600
                hc = hrs / (prod_hours * 5)
                
                # Surplus Logic: Distributes QA count across active workflows in locale
                wf_count = len(f_df[f_df['locale'] == loc]['workflow'].unique())
                
                results.append({
                    "Locale": loc,
                    "Transformation Type": wf,
                    "Exp. Volume": int(vol),
                    "HC Needed": hc,
                    "Surplus/Deficit": (qas_per_site / wf_count) - hc
                })
            
            res_df = pd.DataFrame(results)
            st.dataframe(
                res_df.style.map(lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', subset=['Surplus/Deficit'])
                .format({'HC Needed': '{:.2f}', 'Surplus/Deficit': '{:.2f}'}),
                use_container_width=True
            )
else:
    st.info("Please upload the Mercury CSV to see Site/Locale entries.")
