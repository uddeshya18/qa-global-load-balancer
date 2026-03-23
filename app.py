import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Strategic Capacity Planner", layout="wide")

st.title("📊 Strategic Capacity Planner (Full Range Forecast)")

# --- SIDEBAR: GLOBAL CONTROLS ---
st.sidebar.header("⚙️ Global Settings")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

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
    
    idx_site = next((i for i, c in enumerate(cols) if "site" in c), 0)
    idx_locale = next((i for i, c in enumerate(cols) if "locale" in c or "language" in c), 1)
    idx_wf = next((i for i, c in enumerate(cols) if "workflow" in c or "transformation" in c or "type" in c), 3)
    idx_date = next((i for i, c in enumerate(cols) if "date" in c), 9)
    idx_units = next((i for i, c in enumerate(cols) if "processed units" in c), 13)
    idx_aht = next((i for i, c in enumerate(cols) if "handle time" in c), 16)

    df['site'] = raw_df.iloc[:, idx_site].astype(str).str.strip().str.upper()
    df['locale'] = raw_df.iloc[:, idx_locale].astype(str).str.strip()
    df['workflow'] = raw_df.iloc[:, idx_wf].astype(str).str.strip() 
    df['date_part'] = raw_df.iloc[:, idx_date].astype(str)
    df['units'] = pd.to_numeric(raw_df.iloc[:, idx_units], errors='coerce').fillna(0)
    df['aht'] = pd.to_numeric(raw_df.iloc[:, idx_aht], errors='coerce').fillna(0)

    # 3. GROWTH CALCULATION (SYNCED TO YOUR 8.59% LOGIC)
    all_sites = sorted(df['site'].unique())
    selected_sites = st.sidebar.multiselect("Filter Site:", all_sites, default=all_sites)
    
    site_growth_val = 0.0
    if selected_sites:
        site_data = df[df['site'].isin(selected_sites)]
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

    # 4. FILTERING
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
        
        # Locale Summary
        loc_summary = f_df.groupby(['site', 'locale']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
        loc_summary['Avg Weekly Units'] = (loc_summary['units'] / num_weeks_in_data).astype(int)
        loc_summary['Cleaned AHT (s)'] = loc_summary['aht'].map(lambda x: f"{x:.1f}")
        st.dataframe(loc_summary[['site', 'locale', 'Cleaned AHT (s)', 'Avg Weekly Units']], use_container_width=True, hide_index=True)

        # Transformation Breakdown
        st.markdown("### 🛠️ Transformation Type Breakdown (Historical)")
        wf_summary = f_df.groupby(['site', 'workflow']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
        wf_summary['Avg Weekly Units'] = (wf_summary['units'] / num_weeks_in_data).astype(int)
        wf_summary['Cleaned AHT (s)'] = wf_summary['aht'].map(lambda x: f"{x:.1f}")
        st.dataframe(wf_summary.rename(columns={'workflow': 'Transformation Type'})[['site', 'Transformation Type', 'Cleaned AHT (s)', 'Avg Weekly Units']], use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Future Forecast Explorer")
        
        # UPDATED: Week Range Selection Logic
        week_options = []
        for i in range(4):
            start = current_monday + timedelta(weeks=i)
            end = start + timedelta(days=4)
            week_options.append(f"Week {i+1}: {start.strftime('%d %b')} - {end.strftime('%d %b')}")
        
        selected_week = st.selectbox("Select Forecast Week Range:", week_options)
        week_idx = week_options.index(selected_week) + 1
        
        # Locale Forecast
        forecast_results = []
        for (site, loc), loc_data in f_df.groupby(['site', 'locale']):
            base_units = loc_data['units'].sum() / num_weeks_in_data
            pred_vol = base_units * (1 + (site_growth_val * week_idx))
            aht_val = get_trimmed_mean(loc_data['aht'])
            req_hours = (pred_vol * aht_val) / 3600
            hc_needed = req_hours / (prod_hours * 5)
            
            forecast_results.append({
                "Site": site, "Locale": loc, "Exp. Volume": int(pred_vol), 
                "Utilization %": f"{(req_hours / (qas_per_site * prod_hours * 5)) * 100 if qas_per_site > 0 else 0:.1f}%",
                "HC Needed": f"{hc_needed:.1f}", "Surplus/Deficit": f"{qas_per_site - hc_needed:.1f}"
            })
        st.dataframe(pd.DataFrame(forecast_results), use_container_width=True, hide_index=True)

        # Transformation Forecast
        st.markdown("### 🛠️ Predicted Transformation Breakdown")
        wf_stats = f_df.groupby(['site', 'workflow']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
        wf_forecast = []
        for _, row in wf_stats.iterrows():
            base_wf_units = row['units'] / num_weeks_in_data
            pred_wf_units = base_wf_units * (1 + (site_growth_val * week_idx))
            wf_forecast.append({
                "Site": row['site'], "Transformation": row['workflow'],
                "Exp. Units": int(pred_wf_units), 
                "Req. Hours": f"{(pred_wf_units * row['aht']) / 3600:.1f}"
            })
        st.dataframe(pd.DataFrame(wf_forecast), use_container_width=True, hide_index=True)

else:
    st.info("Please upload your Mercury CSV to begin.")
