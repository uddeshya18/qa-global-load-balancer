import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Capacity Planner", layout="wide")

# ---------------------------------------------------------------------------
# DATA LOADING & POSITION-BASED CLEANING
# ---------------------------------------------------------------------------
def load_and_clean_data(uploaded_file):
    # Load raw data
    df = pd.read_csv(uploaded_file)
    
    # Clean whitespace from all headers
    df.columns = df.columns.str.strip()
    
    # --- POSITION-BASED MAPPING (Safest for Mercury CSVs) ---
    # Based on your image: 
    # Col 0 = Site, Col 1 = Locale, Col 3 = Workflow, Col 13/14 = Processed/AHT
    # We will look for these specifically to avoid KeyErrors
    
    new_df = pd.DataFrame()
    
    # 1. Map Site (Column-1)
    if "Column-1" in df.columns:
        new_df["site"] = df["Column-1"]
    
    # 2. Map Locale (Column-2)
    if "Column-2" in df.columns:
        new_df["locale"] = df["Column-2"]
        
    # 3. Map Workflow (Column-4:Transformation Type)
    wf_col = [c for c in df.columns if "Transformation Type" in c]
    if wf_col:
        new_df["workflow"] = df[wf_col[0]]
        
    # 4. Map Units (The FIRST 'Processed' column)
    # We use .iloc to avoid the 'Duplicate Name' KeyError
    processed_cols = [i for i, col in enumerate(df.columns) if "Processed" in col]
    if processed_cols:
        new_df["units"] = df.iloc[:, processed_cols[0]]
        
    # 5. Map AHT (Average Handle Time)
    aht_cols = [c for c in df.columns if "Average Handle Time" in c]
    if aht_cols:
        new_df["aht"] = df[aht_cols[0]]

    # --- STRING CLEANING LOGIC (From your Efficiency Model) ---
    for col in ["site", "workflow", "locale"]:
        if col in new_df.columns:
            new_df[col] = new_df[col].astype(str).str.strip()
            # Remove null-strings that hide 'en_uk'
            new_df = new_df[new_df[col].notna() & (new_df[col] != "") & (new_df[col] != "nan")]
    
    # --- NUMERIC CONVERSION ---
    new_df["aht"] = pd.to_numeric(new_df["aht"], errors="coerce")
    new_df["units"] = pd.to_numeric(new_df["units"], errors="coerce")
    
    # Drop rows missing critical data
    new_df = new_df.dropna(subset=["aht", "units"])
    new_df = new_df[new_df["units"] > 0].copy()
    
    return new_df

# ---------------------------------------------------------------------------
# MAIN UI
# ---------------------------------------------------------------------------
st.title("📊 Weekly Capacity Planner")

uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type=["csv"])

if uploaded_file:
    df = load_and_clean_data(uploaded_file)
    
    # Verification to ensure 'units' and 'site' were actually created
    if 'units' not in df.columns or 'site' not in df.columns:
        st.error(f"❌ Column detection failed. Columns found: {list(df.columns)}")
        st.stop()

    # Sidebar Global Inputs
    st.sidebar.divider()
    qas_per_site = st.sidebar.number_input("Target QAs per Locale", min_value=1, value=10)
    prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
    growth_per_week = st.sidebar.slider("Weekly Growth (%)", 0, 20, 5)

    # Site & Locale Filters
    all_sites = sorted(df['site'].unique())
    selected_sites = st.sidebar.multiselect("Select Sites:", all_sites, default=all_sites)
    
    relevant_locs = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
    selected_locales = st.sidebar.multiselect("Select Locales:", relevant_locs, default=relevant_locs)
    
    f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

    if f_df.empty:
        st.warning("No data matches selected filters.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical", "🚀 Prediction"])

        with tab1:
            # Historical breakdown by Transformation Type
            hist = f_df.groupby(['locale', 'workflow']).agg({'units':'sum', 'aht':'mean'}).reset_index()
            hist['Avg Weekly Units'] = (hist['units'] / 11).astype(int)
            st.dataframe(hist.style.format({'aht': '{:.1f}'}), use_container_width=True)

        with tab2:
            st.subheader("Future Capacity Forecast")
            
            monday = (datetime.now() + timedelta(days=(0-datetime.now().weekday()) % 7))
            if monday <= datetime.now(): monday += timedelta(days=7)
            
            week_opts = [f"Week {i}: {(monday + timedelta(weeks=i-1)).strftime('%d %b')}" for i in range(1, 5)]
            selected_week = st.selectbox("Select Week:", week_opts)
            w_idx = int(selected_week.split(":")[0].split(" ")[1])

            results = []
            for (loc, wf), group in f_df.groupby(['locale', 'workflow']):
                vol = (group['units'].sum() / 11) * ((1 + (growth_per_week/100))**w_idx)
                aht_val = group['aht'].mean()
                hrs = (vol * aht_val) / 3600
                hc = hrs / (prod_hours * 5)
                
                # Logic for surplus
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
    st.info("Upload CSV to initialize.")
