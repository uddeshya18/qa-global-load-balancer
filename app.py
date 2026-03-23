import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Strategic Capacity Planner", layout="wide")

st.title("📊 Strategic Capacity Planner (Auto-Growth Edition)")
st.markdown(f"### Reporting Date: **{datetime.now().strftime('%A, %b %d, 2026')}**")

# --- SIDEBAR: GLOBAL CONTROLS ---
st.sidebar.header("⚙️ Global Settings")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

qas_per_site = st.sidebar.number_input("Current QAs per Locale", min_value=1, value=10)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)

# --- DYNAMIC MONDAY-FRIDAY DATE LOGIC ---
def get_next_monday(d):
    days_ahead = 0 - d.weekday()
    if days_ahead <= 0: days_ahead += 7
    return d + timedelta(days_ahead)

start_of_week_1 = get_next_monday(datetime.now())

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file)
    
    # Column Detection (Expanded for Dates)
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
    col_date = find_col(["Date", "Day", "Period"], raw_df.columns)

    # Data Cleaning
    df = raw_df[[col_site, col_loc, col_wf, col_aht, col_units, col_date]].copy()
    df.columns = ['site', 'locale', 'workflow', 'aht', 'units', 'date']
    df['site'] = df['site'].astype(str).str.strip().str.upper()
    df['locale'] = df['locale'].astype(str).str.strip()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['aht'] = pd.to_numeric(df['aht'], errors='coerce')
    df['units'] = pd.to_numeric(df['units'], errors='coerce')
    df = df.dropna()

    # --- AUTO-GROWTH CALCULATION ---
    # We find the growth from the first week to the last week in the file
    df['week_start'] = df['date'] - pd.to_timedelta(df['date'].dt.weekday, unit='D')
    weekly_trend = df.groupby(['locale', 'week_start'])['units'].sum().reset_index()
    
    growth_map = {}
    for loc in weekly_trend['locale'].unique():
        loc_trend = weekly_trend[weekly_trend['locale'] == loc].sort_values('week_start')
        if len(loc_trend) > 1:
            first_val = loc_trend.iloc[0]['units']
            last_val = loc_trend.iloc[-1]['units']
            total_weeks = len(loc_trend)
            # Calculate Compound Weekly Growth Rate (CWGR)
            if first_val > 0:
                cwgr = ((last_val / first_val) ** (1 / total_weeks)) - 1
                growth_map[loc] = max(0, cwgr * 100) # Percentage
            else:
                growth_map[loc] = 0
        else:
            growth_map[loc] = 0

    avg_historical_growth = sum(growth_map.values()) / len(growth_map) if growth_map else 0
    
    st.sidebar.divider()
    st.sidebar.info(f"📈 Historical Avg Growth: **{avg_historical_growth:.1f}%**")
    growth_per_week = st.sidebar.slider("Weekly Volume Growth (%)", 0, 20, int(avg_historical_growth))

    # Filters
    selected_sites = st.sidebar.multiselect("Filter by Site:", sorted(df['site'].unique()), default=df['site'].unique())
    available_locales = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
    selected_locales = st.sidebar.multiselect("Filter by Locale:", available_locales, default=available_locales)
    f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    if not f_df.empty:
        tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Future Prediction"])

        with tab1:
            st.subheader("Historical Performance & Trends")
            summary_loc = f_df.groupby('locale').agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            summary_loc['Avg Weekly Units'] = (summary_loc['units'] / 11).astype(int)
            # Injecting the Auto-Growth into the table
            summary_loc['Detected Growth %'] = summary_loc['locale'].map(growth_map)
            
            st.dataframe(summary_loc.rename(columns={'aht': 'Cleaned AHT (s)'}).style.format({
                'Cleaned AHT (s)': '{:.1f}',
                'Detected Growth %': '{:.1f}%'
            }), use_container_width=True, hide_index=True)

        with tab2:
            week_options = [f"Week {i}: {(start_of_week_1 + timedelta(weeks=i-1)).strftime('%d %b')}" for i in range(1, 5)]
            selected_week_str = st.selectbox("Select Forecast Week:", week_options)
            week_idx = int(selected_week_str.split(" ")[1].split(":")[0])
            
            week_results = []
            for loc in f_df['locale'].unique():
                loc_data = f_df[f_df['locale'] == loc]
                base_weekly = loc_data['units'].sum() / 11
                # Use the manual slider for the prediction
                growth_factor = (1 + (growth_per_week / 100)) ** week_idx
                pred_vol = base_weekly * growth_factor
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

else:
    st.info("Upload Mercury CSV to activate the Dynamic Planner.")
