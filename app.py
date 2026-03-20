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

definitions = {
    "HC Needed": "The number of full-time employees required for this specific week's volume.",
    "Cleaned AHT": "The 95th Percentile Trimmed Mean. Removes the slowest 5% of 'glitch' tasks.",
    "Productive Hours": "Actual hours spent processing (excluding breaks/meetings).",
    "Utilization %": "Percentage of available team hours consumed by work. >100% = Understaffed.",
    "Surplus/Deficit": "(+) means extra people; (-) means you need more people."
}

qas_per_site = st.sidebar.number_input("Current QAs per Locale", min_value=1, value=10)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
growth_per_week = st.sidebar.slider("Weekly Volume Growth (%)", 0, 20, 5)

def get_next_monday(d):
    days_ahead = 0 - d.weekday()
    if days_ahead <= 0: days_ahead += 7
    return d + timedelta(days_ahead)

start_of_week_1 = get_next_monday(datetime.now())

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file)
    
    # --- ROBUST COLUMN DETECTION ---
    def find_col(keywords, df_cols):
        for k in keywords:
            for col in df_cols:
                if k.lower() in str(col).lower(): return col
        return None

    col_site = find_col(["Column-1", "Site"], raw_df.columns)
    col_loc = find_col(["Column-2", "Locale"], raw_df.columns)
    col_wf = find_col(["Column-4", "Transformation Type"], raw_df.columns)
    col_aht = find_col(["Average Handle Time", "AHT"], raw_df.columns)
    col_units = find_col(["Processed Units", "Processed"], raw_df.columns)

    # --- DATA CLEANING (Ensuring CBD & Locales show up) ---
    df = raw_df[[col_site, col_loc, col_wf, col_aht, col_units]].copy()
    df.columns = ['site', 'locale', 'workflow', 'aht', 'units']
    
    # Strip spaces and standardize case to prevent hidden duplicates
    for col in ['site', 'locale', 'workflow']:
        df[col] = df[col].astype(str).str.strip().str.upper()

    df['aht'] = pd.to_numeric(df['aht'], errors='coerce')
    df['units'] = pd.to_numeric(df['units'], errors='coerce')
    df = df.dropna(subset=['aht', 'units'])

    # --- UPDATED FILTERS (Cascading Logic) ---
    st.sidebar.divider()
    st.sidebar.subheader("🔍 Filter Data")
    
    unique_sites = sorted(df['site'].unique())
    selected_sites = st.sidebar.multiselect("Filter by Site:", unique_sites, default=unique_sites)
    
    # Filter available locales based on selected sites
    available_locales = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
    selected_locales = st.sidebar.multiselect("Filter by Locale:", available_locales, default=available_locales)
    
    f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    if f_df.empty:
        st.warning("⚠️ No data selected. Please check your Site/Locale filters.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Future Prediction"])

        with tab1:
            st.subheader("Historical Performance Audit")
            # Separated Locale and Workflow Table
            hist_wf = f_df.groupby(['locale', 'workflow'], as_index=False).agg({'units': 'sum', 'aht': get_trimmed_mean})
            hist_wf['Avg Weekly Units'] = (hist_wf['units'] / 11).astype(int)
            st.dataframe(
                hist_wf.rename(columns={'aht': 'Cleaned AHT (s)'}).style.format({'Cleaned AHT (s)': '{:.1f}'}), 
                use_container_width=True, hide_index=True
            )

        with tab2:
            st.subheader("Weekly Forecast Explorer")
            with st.expander("📖 Glossary & Definitions"):
                for term, val in definitions.items():
                    st.write(f"**{term}:** {val}")

            week_options = [f"Week {i}: {(start_of_week_1 + timedelta(weeks=i-1)).strftime('%d %b')} to {(start_of_week_1 + timedelta(weeks=i-1, days=4)).strftime('%d %b')}" for i in range(1, 5)]
            selected_week_str = st.selectbox("Select Forecast Week:", week_options)
            week_idx = int(selected_week_str.split(":")[0].split(" ")[1])
            
            # Prediction Logic
            week_results = []
            for loc in f_df['locale'].unique():
                loc_data = f_df[f_df['locale'] == loc]
                base_weekly = loc_data['units'].sum() / 11
                pred_vol = base_weekly * ((1 + (growth_per_week / 100)) ** week_idx)
                aht_val = get_trimmed_mean(loc_data['aht'])
                req_hours = (pred_vol * aht_val) / 3600
                hc_needed = req_hours / (prod_hours * 5)
                
                week_results.append({
                    "Locale": loc,
                    "Total Exp. Volume": int(pred_vol),
                    "Utilization %": (req_hours / (qas_per_site * prod_hours * 5)) * 100 if qas_per_site > 0 else 0,
                    "HC Needed": hc_needed,
                    "Surplus/Deficit": qas_per_site - hc_needed
                })

            st.markdown("### 📍 Locale Staffing Status")
            res_df = pd.DataFrame(week_results)
            st.dataframe(
                res_df.style.map(lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', subset=['Surplus/Deficit'])
                .format({'Utilization %': '{:.1f}%', 'HC Needed': '{:.1f}', 'Surplus/Deficit': '{:.1f}'}), 
                use_container_width=True, hide_index=True
            )
            
            st.markdown("### 🛠️ Transformation Type Breakdown")
            wf_group = f_df.groupby(['locale', 'workflow'], as_index=False).agg({'units': 'sum', 'aht': get_trimmed_mean})
            wf_details = []
            for _, row in wf_group.iterrows():
                pred_wf_vol = (row['units'] / 11) * ((1 + (growth_per_week / 100)) ** week_idx)
                wf_details.append({
                    "Locale": row['locale'],
                    "Transformation Type": row['workflow'],
                    "Exp. Units": int(pred_wf_vol),
                    "Req. Prod Hours": (pred_wf_vol * row['aht']) / 3600
                })
            st.dataframe(pd.DataFrame(wf_details).style.format({'Req. Prod Hours': '{:.1f}'}), use_container_width=True, hide_index=True)

else:
    st.info("Upload Mercury CSV to activate the Dynamic Planner.")
