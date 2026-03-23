import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Strategic Capacity Planner", layout="wide")

st.title("📊 Strategic Capacity Planner (Manual Sync Edition)")

# --- SIDEBAR: GLOBAL CONTROLS ---
st.sidebar.header("⚙️ Global Settings")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

# User Inputs for Staffing Calculation
qas_per_site = st.sidebar.number_input("Current QAs per Locale", min_value=1, value=10)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)

def get_monday(d):
    return d - timedelta(days=d.weekday())

current_monday = get_monday(datetime.now())

if uploaded_file:
    # 1. LOAD DATA
    raw_df = pd.read_csv(uploaded_file, sep=None, engine='python')
    
    # 2. DYNAMIC COLUMN MAPPING
    df = pd.DataFrame()
    cols = [str(c).lower() for c in raw_df.columns]
    
    # Helper to find column indices based on common Mercury names
    idx_site = next((i for i, c in enumerate(cols) if "site" in c), 0)
    idx_locale = next((i for i, c in enumerate(cols) if "locale" in c or "language" in c), 1)
    idx_wf = next((i for i, c in enumerate(cols) if "workflow" in c or "transformation" in c), 3)
    idx_date = next((i for i, c in enumerate(cols) if "date" in c), 9)
    idx_units = next((i for i, c in enumerate(cols) if "processed units" in c), 13)
    idx_aht = next((i for i, c in enumerate(cols) if "handle time" in c), 16)

    df['site'] = raw_df.iloc[:, idx_site].astype(str).str.strip().str.upper()
    df['locale'] = raw_df.iloc[:, idx_locale].astype(str).str.strip()
    df['workflow'] = raw_df.iloc[:, idx_wf].astype(str).str.strip() 
    df['date_part'] = raw_df.iloc[:, idx_date].astype(str)
    df['units'] = pd.to_numeric(raw_df.iloc[:, idx_units], errors='coerce').fillna(0)
    df['aht'] = pd.to_numeric(raw_df.iloc[:, idx_aht], errors='coerce').fillna(0)

    # 3. SITE SELECTION & GROWTH CALCULATION (THE 8.59% LOGIC)
    all_sites = sorted(df['site'].unique())
    selected_sites = st.sidebar.multiselect("Filter Site:", all_sites, default=all_sites)
    
    site_growth_val = 0.0
    if selected_sites:
        site_data = df[df['site'].isin(selected_sites)]
        # Aggregate by week across the whole site
        site_weekly = site_data.groupby('date_part')['units'].sum().reset_index().sort_values('date_part')
        u = site_weekly['units'].values
        
        if len(u) > 1:
            diffs = []
            for i in range(1, len(u)):
                if u[i-1] > 0:
                    raw_change = (u[i] - u[i-1]) / u[i-1]
                    # THE SYNC RULES: Cap at 20%, Floor at 0%
                    capped_change = min(max(0, raw_change), 0.20)
                    diffs.append(capped_change)
            site_growth_val = np.mean(diffs) if diffs else 0.0

    st.sidebar.metric(label="📈 Estimated Growth (Selected)", value=f"{site_growth_val * 100:.2f}%")
    st.sidebar.divider()

    # 4. DATA FILTERING
    f_df = df[df['site'].isin(selected_sites)]
    all_locales = sorted(f_df['locale'].unique())
    selected_locales = st.sidebar.multiselect("Filter Locale:", all_locales, default=all_locales)
    f_df = f_df[f_df['locale'].isin(selected_locales)]
    num_weeks_in_data = len(df['date_part'].unique())

    # 5. TABS
    tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Future Prediction"])

    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    with tab1:
        st.subheader("Historical Verification")
        # Weekly Unit breakdown table to confirm manual math
        weekly_v = f_df.groupby('date_part')['units'].sum().reset_index()
        weekly_v.columns = ['Week Starting', 'Total Site Units']
        st.table(weekly_v)

        loc_summary = f_df.groupby(['site', 'locale']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
        loc_summary['Avg Weekly Units'] = (loc_summary['units'] / num_weeks_in_data).astype(int)
        loc_summary['Cleaned AHT (s)'] = loc_summary['aht'].map(lambda x: f"{x:.1f}")
        st.dataframe(loc_summary[['site', 'locale', 'Cleaned AHT (s)', 'Avg Weekly Units']], use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Future Forecast Explorer")
        week_labels = [f"Week {i+1}: {(current_monday + timedelta(weeks=i)).strftime('%d %b')}" for i in range(4)]
        selected_week = st.selectbox("Select Forecast Week:", week_labels)
        week_idx = week_labels.index(selected_week) + 1
        
        forecast_results = []
        for (site, loc), loc_data in f_df.groupby(['site', 'locale']):
            base_units = loc_data['units'].sum() / num_weeks_in_data
            # We apply the Site-level synced growth
            pred_vol = base_units * (1 + (site_growth_val * week_idx))
            
            aht_val = get_trimmed_mean(loc_data['aht'])
            req_hours = (pred_vol * aht_val) / 3600
            hc_needed = req_hours / (prod_hours * 5)
            
            forecast_results.append({
                "Site": site, "Locale": loc, "Est. Growth": f"{site_growth_val*100:.2f}%", 
                "Exp. Volume": int(pred_vol), 
                "Utilization %": f"{(req_hours / (qas_per_site * prod_hours * 5)) * 100 if qas_per_site > 0 else 0:.1f}%",
                "HC Needed": f"{hc_needed:.1f}", "Surplus/Deficit": f"{qas_per_site - hc_needed:.1f}"
            })
        st.dataframe(pd.DataFrame(forecast_results), use_container_width=True, hide_index=True)

else:
    st.info("Please upload your Mercury CSV to begin.")
