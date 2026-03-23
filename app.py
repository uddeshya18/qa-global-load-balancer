import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Strategic Capacity Planner", layout="wide")

st.title("📊 Strategic Capacity Planner (Dynamic Site Growth)")

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
    
    # 2. COLUMN MAPPING (Positional for Mercury)
    df = pd.DataFrame()
    df['site'] = raw_df.iloc[:, 0].astype(str).str.strip().str.upper()
    df['locale'] = raw_df.iloc[:, 1].astype(str).str.strip()
    df['workflow'] = raw_df.iloc[:, 3].astype(str).str.strip() # Column-4
    
    cols = [str(c).lower() for c in raw_df.columns]
    idx_date = next((i for i, c in enumerate(cols) if "date" in c), 9)
    idx_units = next((i for i, c in enumerate(cols) if "processed units" in c), 13)
    idx_aht = next((i for i, c in enumerate(cols) if "handle time" in c), 16)

    df['date_part'] = raw_df.iloc[:, idx_date].astype(str)
    df['units'] = pd.to_numeric(raw_df.iloc[:, idx_units], errors='coerce').fillna(0)
    df['aht'] = pd.to_numeric(raw_df.iloc[:, idx_aht], errors='coerce').fillna(0)

    # 3. CALCULATE GROWTH PER SITE/LOCALE
    growth_map = {}
    unique_weeks = sorted(df['date_part'].unique())
    num_weeks_in_data = len(unique_weeks) if len(unique_weeks) > 0 else 1

    for (s, l), group in df.groupby(['site', 'locale']):
        loc_trend = group.groupby('date_part')['units'].sum().reset_index()
        if len(loc_trend) > 1:
            first = loc_trend.iloc[0]['units']
            last = loc_trend.iloc[-1]['units']
            rate = ((last / first) ** (1 / len(loc_trend))) - 1 if first > 0 else 0
            growth_map[(s, l)] = max(0, rate) 
        else:
            growth_map[(s, l)] = 0

    # --- NEW SIDEBAR BOX: ESTIMATED GROWTH ---
    st.sidebar.divider()
    # Filter sites first to get relevant growth
    all_sites = sorted(df['site'].unique())
    selected_sites = st.sidebar.multiselect("Filter Site:", all_sites, default=all_sites)
    
    # Calculate Average Growth for selected sites
    if selected_sites:
        relevant_growth = [v for k, v in growth_map.items() if k[0] in selected_sites]
        avg_growth = (sum(relevant_growth) / len(relevant_growth)) * 100 if relevant_growth else 0
        st.sidebar.metric(label="📈 Estimated Growth (Selected)", value=f"{avg_growth:.1f}%")
    
    st.sidebar.divider()
    
    # 4. REMAINING FILTERS
    f_df = df[df['site'].isin(selected_sites)]
    all_locales = sorted(f_df['locale'].unique())
    selected_locales = st.sidebar.multiselect("Filter Locale:", all_locales, default=all_locales)
    f_df = f_df[f_df['locale'].isin(selected_locales)]

    # 5. TABS
    tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Future Prediction"])

    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    with tab1:
        st.subheader("Historical Audit")
        
        st.markdown("### 📍 Locale Level Performance")
        loc_summary = f_df.groupby(['site', 'locale']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
        loc_summary['Avg Weekly Units'] = (loc_summary['units'] / num_weeks_in_data).astype(int)
        loc_summary['Est. Growth %'] = loc_summary.apply(lambda x: f"{growth_map.get((x['site'], x['locale']), 0)*100:.1f}%", axis=1)
        st.dataframe(loc_summary.rename(columns={'aht': 'Cleaned AHT (s)'}).style.format({'Cleaned AHT (s)': '{:.1f}'}), use_container_width=True, hide_index=True)

        st.markdown("### 🛠️ Transformation Type Breakdown")
        wf_summary = f_df.groupby(['site', 'workflow']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
        st.dataframe(wf_summary.rename(columns={'workflow': 'Transformation Type', 'aht': 'Cleaned AHT (s)'}).style.format({'Cleaned AHT (s)': '{:.1f}'}), use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Future Forecast Explorer")
        
        week_labels = [f"Week {i+1}: {(current_monday + timedelta(weeks=i)).strftime('%d %b')} - {(current_monday + timedelta(weeks=i, days=4)).strftime('%d %b')}" for i in range(4)]
        selected_week = st.selectbox("Select Forecast Week:", week_labels)
        week_idx = week_labels.index(selected_week) + 1
        
        st.markdown("### 📍 Predicted Staffing Status")
        forecast_results = []
        for (site, loc), loc_data in f_df.groupby(['site', 'locale']):
            loc_growth = growth_map.get((site, loc), 0)
            base_units = loc_data['units'].sum() / num_weeks_in_data
            pred_vol = base_units * ((1 + loc_growth) ** week_idx)
            aht_val = get_trimmed_mean(loc_data['aht'])
            req_hours = (pred_vol * aht_val) / 3600
            hc_needed = req_hours / (prod_hours * 5)
            forecast_results.append({
                "Site": site, "Locale": loc, "Est. Growth %": f"{loc_growth*100:.1f}%", 
                "Exp. Volume": int(pred_vol), "Utilization %": (req_hours / (qas_per_site * prod_hours * 5)) * 100 if qas_per_site > 0 else 0,
                "HC Needed": hc_needed, "Surplus/Deficit": qas_per_site - hc_needed
            })
        st.dataframe(pd.DataFrame(forecast_results).style.format({'Utilization %': '{:.1f}%', 'HC Needed': '{:.1f}', 'Surplus/Deficit': '{:.1f}'}), use_container_width=True, hide_index=True)

        st.markdown("### 🛠️ Predicted Transformation Breakdown")
        # FIXED ERROR: This section now handles the multi-index correctly
        wf_stats = f_df.groupby(['site', 'locale', 'workflow']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
        wf_forecast = []
        for _, row in wf_stats.iterrows():
            loc_growth = growth_map.get((row['site'], row['locale']), 0)
            base_wf_units = row['units'] / num_weeks_in_data
            pred_wf_units = base_wf_units * ((1 + loc_growth) ** week_idx)
            wf_forecast.append({
                "Site": row['site'], "Locale": row['locale'], "Transformation": row['workflow'],
                "Est. Growth %": f"{loc_growth*100:.1f}%", "Exp. Units": int(pred_wf_units), "Req. Hours": (pred_wf_units * row['aht']) / 3600
            })
        st.dataframe(pd.DataFrame(wf_forecast).style.format({'Req. Hours': '{:.1f}'}), use_container_width=True, hide_index=True)

else:
    st.info("Upload Mercury CSV to activate.")
