import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Capacity Planner", layout="wide")

# ---------------------------------------------------------------------------
# DATA LOADING (LOCALE PERSISTENCE LOGIC)
# ---------------------------------------------------------------------------
def load_and_clean_data(uploaded_file):
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()
    
    new_df = pd.DataFrame()
    
    # 1. POSITIONAL MAPPING (Ensures we find the columns regardless of exact names)
    try:
        new_df["site"] = df.iloc[:, 0].astype(str).str.strip()
        new_df["locale"] = df.iloc[:, 1].astype(str).str.strip()
        
        # Finding Transformation Type (Column-4)
        wf_col = [c for c in df.columns if "Transformation" in c]
        new_df["workflow"] = df[wf_col[0]] if wf_col else df.iloc[:, 3]
        new_df["workflow"] = new_df["workflow"].astype(str).str.strip()
        
        # Finding Processed (Units) and AHT
        proc_cols = [c for c in df.columns if "Processed" in c]
        new_df["units"] = df[proc_cols[0]] if proc_cols else df.iloc[:, 13]
        
        aht_cols = [c for c in df.columns if "Average Handle Time" in c]
        new_df["aht"] = df[aht_cols[0]] if aht_cols else df.iloc[:, 15]
    except Exception as e:
        st.error(f"Mapping Error: {e}")
        st.stop()

    # 2. STRING CLEANING (Removing 'nan' but keeping valid strings)
    for col in ["site", "workflow", "locale"]:
        new_df = new_df[new_df[col].notna() & (new_df[col].str.lower() != "nan") & (new_df[col] != "")]

    # 3. NUMERIC CONVERSION (Keep the rows, fill NaN with 0 so they don't disappear)
    new_df["aht"] = pd.to_numeric(new_df["aht"], errors="coerce").fillna(0)
    new_df["units"] = pd.to_numeric(new_df["units"], errors="coerce").fillna(0)
    
    return new_df

# ---------------------------------------------------------------------------
# MAIN UI
# ---------------------------------------------------------------------------
st.title("📊 Weekly Capacity Planner")

uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type=["csv"])

if uploaded_file:
    df = load_and_clean_data(uploaded_file)
    
    # SIDEBAR CONTROLS
    st.sidebar.divider()
    qas_per_site = st.sidebar.number_input("Target QAs per Locale", min_value=1, value=10)
    prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
    growth_per_week = st.sidebar.slider("Weekly Growth (%)", 0, 20, 5)

    # --- THE FILTER LOGIC ---
    # Get unique sites
    all_sites = sorted(df['site'].unique())
    selected_sites = st.sidebar.multiselect("1. Select Sites:", all_sites, default=all_sites)
    
    # CRITICAL: Find locales linked to selected sites BEFORE any volume filtering
    relevant_locs = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
    
    # Display the multiselect - en_uk should now appear here
    selected_locales = st.sidebar.multiselect("2. Select Locales:", relevant_locs, default=relevant_locs)
    
    # Filter the main dataframe
    f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

    if f_df.empty:
        st.warning("No data matches selected filters.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical View", "🚀 Forecast Prediction"])

        with tab1:
            st.subheader("Historical Workflow Breakdown")
            # Aggregation (Grouping by Locale and Transformation Type)
            summary = f_df.groupby(['locale', 'workflow']).agg({'units': 'sum', 'aht': 'mean'}).reset_index()
            summary['Avg Weekly Vol'] = (summary['units'] / 11).astype(int)
            st.dataframe(summary.style.format({'aht': '{:.1f}'}), use_container_width=True)

        with tab2:
            st.subheader("Future Capacity Forecast")
            
            monday = (datetime.now() + timedelta(days=(0-datetime.now().weekday()) % 7))
            if monday <= datetime.now(): monday += timedelta(days=7)
            
            week_opts = [f"Week {i}: {(monday + timedelta(weeks=i-1)).strftime('%d %b')}" for i in range(1, 5)]
            selected_week = st.selectbox("Select Week:", week_opts)
            w_idx = int(selected_week.split(":")[0].split(" ")[1])

            results = []
            for (loc, wf), group in f_df.groupby(['locale', 'workflow']):
                # If units/aht are 0, we still show the row but HC will be 0
                vol = (group['units'].sum() / 11) * ((1 + (growth_per_week/100))**w_idx)
                aht_val = group['aht'].mean()
                
                # Math check to prevent division by zero
                hrs = (vol * aht_val) / 3600 if aht_val > 0 else 0
                hc = hrs / (prod_hours * 5) if prod_hours > 0 else 0
                
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
    st.info("Please upload the CSV. Ensure 'Column-1' contains the Site and 'Column-2' contains the Locale.")
