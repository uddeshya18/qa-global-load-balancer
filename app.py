import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Workflow Forecast", layout="wide")

st.title("🔮 Weekly Strategic Capacity Forecast")
st.markdown(f"### Reporting Date: **{datetime.now().strftime('%B %d, 2026')}**")

# --- SIDEBAR: GLOBAL CONTROLS ---
st.sidebar.header("⚙️ Global Settings")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

# Hover Definitions (Generic Definitions)
hc_def = "Headcount (HC) Needed: Total people required to finish the volume based on AHT and Productive Hours."
aht_def = "Cleaned AHT: The 95th Percentile Trimmed Mean. This removes technical 'outliers' (glitches) to show true speed."
prod_def = "Productive Hours: The actual time per day a QA spends processing tasks (excludes breaks/meetings)."

qas_per_site = st.sidebar.number_input("Current QAs per Locale", min_value=1, value=10, help=hc_def)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5, help=prod_def)
growth_per_week = st.sidebar.slider("Weekly Volume Growth (%)", 0, 20, 5, help="Compounding growth expected each week.")

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file)
    
    # 1. SMART COLUMN DETECTION
    def find_col(keywords, df_cols):
        for k in keywords:
            for col in df_cols:
                if k.lower() in col.lower(): return col
        return None

    col_site = find_col(["Column-1", "Site"], raw_df.columns)
    col_loc = find_col(["Column-2", "Locale"], raw_df.columns)
    col_wf = find_col(["Column-4", "Transformation Type"], raw_df.columns)
    col_aht = find_col(["Average Handle Time", "AHT"], raw_df.columns)
    col_units = find_col(["Processed Units", "Processed"], raw_df.columns)

    df = raw_df[[col_site, col_loc, col_wf, col_aht, col_units]].copy()
    df.columns = ['site', 'locale', 'workflow', 'aht', 'units']
    df['aht'] = pd.to_numeric(df['aht'], errors='coerce')
    df['units'] = pd.to_numeric(df['units'], errors='coerce')
    df = df.dropna(subset=['aht', 'units'])

    # 2. DYNAMIC FILTERS
    st.sidebar.divider()
    st.sidebar.subheader("🔍 Filter Data")
    selected_sites = st.sidebar.multiselect("Filter by Site:", sorted(df['site'].unique()), default=df['site'].unique())
    selected_locales = st.sidebar.multiselect("Filter by Locale:", sorted(df[df['site'].isin(selected_sites)]['locale'].unique()), default=df[df['site'].isin(selected_sites)]['locale'].unique())
    f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    if f_df.empty:
        st.warning("⚠️ No data selected. Please check filters.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Weekly Workflow Predictions"])

        with tab1:
            st.subheader("Historical Performance (Jan 1 - Mar 18)")
            # Basic Locale Summary
            summary_loc = f_df.groupby('locale').agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            summary_loc['Avg Weekly Units'] = (summary_loc['units'] / 11).astype(int)
            st.dataframe(summary_loc.rename(columns={'aht': 'Cleaned AHT (s)'}), use_container_width=True)
            
            st.write("### 🛠️ Workflow Level Audit")
            hist_wf = f_df.groupby(['locale', 'workflow']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            st.dataframe(hist_wf.rename(columns={'aht': 'Cleaned AHT (s)'}), use_container_width=True)

        with tab2:
            st.subheader("4-Week Rolling Forecast (Granular Breakdown)")
            st.info(f"💡 {hc_def} | {aht_def}")
            
            current_date = datetime.now()
            
            for i in range(1, 5):
                start_w = current_date + timedelta(weeks=i-1)
                end_w = current_date + timedelta(weeks=i)
                st.write(f"## 📅 Week {i}: {start_w.strftime('%d %b')} — {end_w.strftime('%d %b')}")
                
                # --- CALCULATION LOGIC ---
                # A. Locale Summary for the Week
                week_results = []
                for loc in f_df['locale'].unique():
                    loc_data = f_df[f_df['locale'] == loc]
                    base_weekly = loc_data['units'].sum() / 11
                    growth_factor = (1 + (growth_per_week / 100)) ** i
                    pred_vol = base_weekly * growth_factor
                    aht_val = get_trimmed_mean(loc_data['aht'])
                    req_hours = (pred_vol * aht_val) / 3600
                    hc_needed = req_hours / (prod_hours * 5)
                    
                    week_results.append({
                        "Locale": loc,
                        "Total Exp. Volume": int(pred_vol),
                        "Utilization %": round((req_hours / (qas_per_site * prod_hours * 5)) * 100, 1),
                        "HC Needed": round(hc_needed, 1),
                        "Surplus/Deficit": round(qas_per_site - hc_needed, 1)
                    })
                
                st.write("**Locale Staffing Status**")
                st.dataframe(pd.DataFrame(week_results).style.applymap(lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', subset=['Surplus/Deficit']), use_container_width=True)

                # B. Workflow Breakdown for the Week
                st.write("**Workflow Hour Requirements**")
                wf_details = []
                wf_group = f_df.groupby(['locale', 'workflow']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
                
                for _, row in wf_group.iterrows():
                    base_wf_vol = row['units'] / 11
                    pred_wf_vol = base_wf_vol * ((1 + (growth_per_week / 100)) ** i)
                    req_hrs_wf = (pred_wf_vol * row['aht']) / 3600
                    
                    wf_details.append({
                        "Locale": row['locale'],
                        "Transformation Type": row['workflow'],
                        "Cleaned AHT": round(row['aht'], 1),
                        "Exp. Units": int(pred_wf_vol),
                        "Req. Prod Hours": round(req_hrs_wf, 1)
                    })
                
                st.dataframe(pd.DataFrame(wf_details).sort_values(['Locale', 'Req. Prod Hours'], ascending=[True, False]), use_container_width=True)
                st.divider()

else:
    st.info("Upload CSV to generate the Granular Weekly Forecast.")
