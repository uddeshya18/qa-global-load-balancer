import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Capacity Planner", layout="wide")

st.title("🔮 Strategic Capacity Planner (Mon-Fri)")
st.markdown(f"### Reporting Date: **{datetime.now().strftime('%A, %b %d, 2026')}**")

# --- SIDEBAR: GLOBAL CONTROLS ---
st.sidebar.header("⚙️ Global Settings")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

qas_per_site = st.sidebar.number_input("Current QAs per Locale", min_value=1, value=10)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
growth_per_week = st.sidebar.slider("Weekly Volume Growth (%)", 0, 20, 5)

# --- DYNAMIC MONDAY-FRIDAY DATE LOGIC ---
def get_next_monday(d):
    days_ahead = 0 - d.weekday()
    if days_ahead <= 0: days_ahead += 7
    return d + timedelta(days_ahead)

start_of_week_1 = get_next_monday(datetime.now())

if uploaded_file:
    # Load raw data
    raw_df = pd.read_csv(uploaded_file)
    
    # 1. COLUMN DETECTION
    def find_col(keywords, df_cols):
        for k in keywords:
            for col in df_cols:
                if k.lower() in col.lower(): return col
        return None

    c_site = find_col(["Column-1", "Site"], raw_df.columns)
    c_loc = find_col(["Column-2", "Locale"], raw_df.columns)
    c_wf = find_col(["Column-4", "Transformation Type"], raw_df.columns)
    c_aht = find_col(["Average Handle Time", "AHT"], raw_df.columns)
    c_units = find_col(["Processed Units", "Processed"], raw_df.columns)

    # 2. THE "NO-DROP" DATA CLEANING
    # We create a copy and normalize strings to prevent hidden mismatches
    df = raw_df[[c_site, c_loc, c_wf, c_aht, c_units]].copy()
    df.columns = ['site', 'locale', 'workflow', 'aht', 'units']
    
    df['site'] = df['site'].fillna("UNKNOWN").astype(str).str.strip().str.upper()
    df['locale'] = df['locale'].fillna("UNKNOWN").astype(str).str.strip().str.lower()
    df['workflow'] = df['workflow'].fillna("GENERAL").astype(str).str.strip()
    
    # Convert numbers but DO NOT drop rows yet
    df['aht'] = pd.to_numeric(df['aht'], errors='coerce').fillna(0)
    df['units'] = pd.to_numeric(df['units'], errors='coerce').fillna(0)

    # 3. ROBUST FILTERING
    st.sidebar.divider()
    st.sidebar.subheader("🔍 Data Visibility")
    
    # Emergency Toggle: If you can't find something, turn this ON
    show_all = st.sidebar.checkbox("Show All Data (Ignore Filters)", value=False)
    
    all_sites = sorted(df['site'].unique())
    selected_sites = st.sidebar.multiselect("Select Sites:", all_sites, default=all_sites)
    
    # Only show locales belonging to selected sites
    relevant_locales = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
    selected_locales = st.sidebar.multiselect("Select Locales:", relevant_locales, default=relevant_locales)
    
    # Apply Filtering
    if show_all:
        f_df = df.copy()
    else:
        f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

    def get_trimmed_mean(group):
        # Only trim if we have enough data, otherwise return mean
        clean_group = group[group > 0]
        if len(clean_group) < 5: return clean_group.mean() if not clean_group.empty else 0
        return clean_group[clean_group <= clean_group.quantile(0.95)].mean()

    # 4. DATA VALIDATION SUMMARY (Check if your missing locale is here!)
    with st.expander("🛠️ Data Debugger: See All Detected Entries"):
        col1, col2 = st.columns(2)
        col1.write("**All Sites Found:**")
        col1.write(all_sites)
        col2.write("**All Locales Found:**")
        col2.write(sorted(df['locale'].unique()))

    if f_df.empty:
        st.error("❌ No data matches these filters.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Future Prediction"])

        with tab1:
            st.subheader("Historical Performance")
            # Grouping
            summary_loc = f_df.groupby('locale').agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            summary_loc['Avg Weekly Units'] = (summary_loc['units'] / 11).astype(int)
            st.dataframe(summary_loc.style.format({'aht': '{:.1f}'}), use_container_width=True)

        with tab2:
            # Week Selection
            week_options = [f"Week {i}: {(start_of_week_1 + timedelta(weeks=i-1)).strftime('%d %b')} - {(start_of_week_1 + timedelta(weeks=i-1, days=4)).strftime('%d %b')}" for i in range(1, 5)]
            selected_week = st.selectbox("Select Prediction Week:", week_options)
            week_idx = int(selected_week.split(":")[0].split(" ")[1])

            week_results = []
            for loc in f_df['locale'].unique():
                loc_data = f_df[f_df['locale'] == loc]
                
                # Math
                base_weekly = loc_data['units'].sum() / 11
                growth = (1 + (growth_per_week / 100)) ** week_idx
                pred_vol = base_weekly * growth
                aht_val = get_trimmed_mean(loc_data['aht'])
                
                req_hours = (pred_vol * aht_val) / 3600
                hc_needed = req_hours / (prod_hours * 5)
                
                week_results.append({
                    "Locale": loc,
                    "Exp. Volume": int(pred_vol),
                    "Utilization %": (req_hours / (qas_per_site * prod_hours * 5)) * 100 if qas_per_site > 0 else 0,
                    "HC Needed": hc_needed,
                    "Surplus/Deficit": qas_per_site - hc_needed
                })

            st.dataframe(
                pd.DataFrame(week_results).style.map(lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', subset=['Surplus/Deficit'])
                .format({'Utilization %': '{:.1f}%', 'HC Needed': '{:.1f}', 'Surplus/Deficit': '{:.1f}'}),
                use_container_width=True
            )
else:
    st.info("Upload CSV to view all entries.")
