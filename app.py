import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Capacity Planner", layout="wide")

# ---------------------------------------------------------------------------
# 1. FIXED COLUMN MAPPING (Based on your Screenshot)
# ---------------------------------------------------------------------------
COLUMN_MAPPING = {
    "Column-1": "site",
    "Column-2": "locale",
    "Column-4:Transformation Type": "workflow",
    "Average Handle Time(In Secs)": "aht",
    "Processed": "units",
}

# ---------------------------------------------------------------------------
# 2. DATA LOADING & CLEANING LOGIC (From your Efficiency Model)
# ---------------------------------------------------------------------------
def load_and_clean_data(uploaded_file):
    # Read CSV
    df = pd.read_csv(uploaded_file)
    
    # Clean whitespace from headers first
    df.columns = df.columns.str.strip()
    
    # If there are duplicate 'Processed' columns, rename them to handle the first one
    cols = []
    count = 0
    for col in df.columns:
        if col == "Processed":
            cols.append(f"Processed_{count}" if count > 0 else "Processed")
            count += 1
        else:
            cols.append(col)
    df.columns = cols

    # Apply your mapping
    df = df.rename(columns=COLUMN_MAPPING)
    
    # Specific cleaning logic for strings (Handles 'nan' and empty cells)
    for col in ["site", "workflow", "locale"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df = df[df[col].notna() & (df[col] != "") & (df[col] != "nan")]
    
    # Numeric conversion
    df["aht"] = pd.to_numeric(df["aht"], errors="coerce")
    df["units"] = pd.to_numeric(df["units"], errors="coerce")
    
    # Filter out rows with zero/null volume or AHT
    df = df.dropna(subset=["aht", "units"])
    df = df[df["units"] > 0].copy()
    
    return df

# ---------------------------------------------------------------------------
# 3. MAIN APPLICATION UI
# ---------------------------------------------------------------------------
st.title("📊 Weekly Capacity Planner")
st.markdown("### Strategic Load Balancer (Mon-Fri)")

# Sidebar Configuration
st.sidebar.header("⚙️ Data Settings")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type=["csv"])

if uploaded_file:
    # Process data using the integrated logic
    df = load_and_clean_data(uploaded_file)
    
    # Verification check to prevent KeyErrors
    if 'site' not in df.columns or 'locale' not in df.columns:
        st.error(f"❌ Mapping Error. Found columns: {list(df.columns)}")
        st.stop()

    # Sidebar Global Inputs
    st.sidebar.divider()
    qas_per_site = st.sidebar.number_input("Target QAs per Locale", min_value=1, value=10)
    prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
    growth_per_week = st.sidebar.slider("Weekly Volume Growth (%)", 0, 20, 5)

    # Site & Locale Filters (Logic as per your model)
    all_sites = sorted(df['site'].unique())
    selected_sites = st.sidebar.multiselect("1. Select Sites:", all_sites, default=all_sites)
    
    # Filter locales based on site selection
    relevant_locs = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
    selected_locales = st.sidebar.multiselect("2. Select Locales:", relevant_locs, default=relevant_locs)
    
    # Final Filtered Dataset
    f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

    if f_df.empty:
        st.warning("No data matches selected filters.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical View", "🚀 Forecast Prediction"])

        with tab1:
            st.subheader("Historical Performance (Jan-Mar)")
            # Aggregation logic
            hist_wf = f_df.groupby(['locale', 'workflow']).agg({
                'units': 'sum', 
                'aht': 'mean'
            }).reset_index()
            
            hist_wf['Avg Weekly Units'] = (hist_wf['units'] / 11).astype(int)
            st.dataframe(hist_wf.style.format({'aht': '{:.1f}'}), use_container_width=True)

        with tab2:
            st.subheader("Future Capacity Forecast")
            
            # Forecast Date Calculation
            today = datetime.now()
            next_monday = today + timedelta(days=(0 - today.weekday()) % 7)
            if next_monday <= today: next_monday += timedelta(days=7)
            
            week_opts = [f"Week {i}: {(next_monday + timedelta(weeks=i-1)).strftime('%d %b')}" for i in range(1, 5)]
            selected_week = st.selectbox("Forecast Horizon:", week_opts)
            w_idx = int(selected_week.split(":")[0].split(" ")[1])

            # Prediction Calculations
            pred_results = []
            for (loc, wf), group in f_df.groupby(['locale', 'workflow']):
                # Growth Factor Calculation
                base_vol = group['units'].sum() / 11
                growth_multiplier = (1 + (growth_per_week/100))**w_idx
                p_vol = base_vol * growth_multiplier
                
                # Capacity Required
                p_aht = group['aht'].mean()
                req_hours = (p_vol * p_aht) / 3600
                hc_needed = req_hours / (prod_hours * 5)
                
                # Logic for calculating surplus based on total QAs per locale
                num_wfs_in_loc = len(f_df[f_df['locale'] == loc]['workflow'].unique())
                
                pred_results.append({
                    "Locale": loc,
                    "Transformation Type": wf,
                    "Exp. Vol": int(p_vol),
                    "HC Needed": hc_needed,
                    "Surplus/Deficit": (qas_per_site / num_wfs_in_loc) - hc_needed
                })
            
            res_df = pd.DataFrame(pred_results)
            st.dataframe(
                res_df.style.map(
                    lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', 
                    subset=['Surplus/Deficit']
                ).format({'HC Needed': '{:.2f}', 'Surplus/Deficit': '{:.2f}'}),
                use_container_width=True
            )

else:
    st.info("Upload Mercury CSV to initialize calculations.")
