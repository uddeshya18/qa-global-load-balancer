import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Strategic Capacity Planner", layout="wide")

st.title("📊 Strategic Capacity Planner (Mercury Edition)")
st.markdown(f"### Reporting Date: **{datetime.now().strftime('%A, %b %d, 2026')}**")

# --- SIDEBAR: GLOBAL CONTROLS ---
st.sidebar.header("⚙️ Global Settings")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

qas_per_site = st.sidebar.number_input("Current QAs per Locale", min_value=1, value=10)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)

def get_next_monday(d):
    days_ahead = 0 - d.weekday()
    if days_ahead <= 0: days_ahead += 7
    return d + timedelta(days_ahead)

start_of_week_1 = get_next_monday(datetime.now())

if uploaded_file:
    # 1. READ DATA
    raw_df = pd.read_csv(uploaded_file)
    
    # 2. EXACT MAPPING FROM YOUR SCREENSHOT
    col_site = "Column-1"
    col_loc = "Column-2"
    col_wf = "Column-4:Transformation Type"
    col_date = "Select Date Part"
    col_units = "Processed Units"
    col_aht = "Average Handle Time(In Secs)"

    try:
        # Extract and Rename for the Engine
        df = raw_df[[col_site, col_loc, col_wf, col_aht, col_units, col_date]].copy()
        df.columns = ['site', 'locale', 'workflow', 'aht', 'units', 'date_str']
        
        # Data Type Cleaning
        df['site'] = df['site'].astype(str).str.strip().str.upper()
        df['locale'] = df['locale'].astype(str).str.strip()
        df['aht'] = pd.to_numeric(df['aht'], errors='coerce').fillna(0)
        df['units'] = pd.to_numeric(df['units'], errors='coerce').fillna(0)
        
        # Logic: Count unique weeks to find the baseline
        unique_weeks = df['date_str'].unique()
        num_weeks = len(unique_weeks) if len(unique_weeks) > 0 else 1

        # 3. AUTO-GROWTH CALCULATION (First Week vs Last Week)
        growth_map = {}
        weekly_trend = df.groupby(['locale', 'date_str'])['units'].sum().reset_index()
        
        for loc in weekly_trend['locale'].unique():
            loc_trend = weekly_trend[weekly_trend['locale'] == loc]
            if len(loc_trend) > 1:
                first_val = loc_trend.iloc[0]['units']
                last_val = loc_trend.iloc[-1]['units']
                if first_val > 0:
                    # Simple Compound Weekly Growth Rate calculation
                    growth_rate = ((last_val / first_val) ** (1 / len(loc_trend))) - 1
                    growth_map[loc] = max(0, growth_rate * 100)
                else: growth_map[loc] = 0
            else: growth_map[loc] = 0

        avg_historical_growth = sum(growth_map.values()) / len(growth_map) if growth_map else 0
        
        st.sidebar.divider()
        st.sidebar.info(f"📈 Detected Growth Trend: **{avg_historical_growth:.1f}%**")
        growth_per_week = st.sidebar.slider("Apply Future Growth (%)", 0, 20, int(avg_historical_growth))

        # 4. FILTERS
        st.sidebar.subheader("🔍 Filter Data")
        selected_sites = st.sidebar.multiselect("Filter Site:", sorted(df['site'].unique()), default=df['site'].unique())
        available_locales = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
        selected_locales = st.sidebar.multiselect("Filter Locale:", available_locales, default=available_locales)
        
        f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

        # 5. TABS
        if not f_df.empty:
            tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Future Prediction"])
            
            def get_trimmed_mean(group):
                if len(group) < 3: return group.median()
                return group[group <= group.quantile(0.95)].mean()

            with tab1:
                st.subheader("Historical Performance (Based on Processed Units)")
                summary_loc = f_df.groupby('locale').agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
                summary_loc['Avg Weekly Units'] = (summary_loc['units'] / num_weeks).astype(int)
                summary_loc['Observed Growth %'] = summary_loc['locale'].map(growth_map)
                
                st.dataframe(summary_loc.rename(columns={'aht': 'Cleaned AHT (s)'}).style.format({
                    'Cleaned AHT (s)': '{:.1f}', 'Observed Growth %': '{:.1f}%'
                }), use_container_width=True, hide_index=True)

            with tab2:
                week_options = [f"Week {i}: Forecast" for i in range(1, 5)]
                selected_week_str = st.selectbox("Select Forecast Week:", week_options)
                week_idx = int(selected_week_str.split(" ")[1].split(":")[0])
                
                week_results = []
                for loc in f_df['locale'].unique():
                    loc_data = f_df[f_df['locale'] == loc]
                    base_weekly = loc_data['units'].sum() / num_weeks
                    growth_factor = (1 + (growth_per_week / 100)) ** week_idx
                    pred_vol = base_weekly * growth_factor
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

                st.markdown("### 📍 Locale Staffing Status")
                st.dataframe(pd.DataFrame(week_results).style.format({
                    'Utilization %': '{:.1f}%', 'HC Needed': '{:.1f}', 'Surplus/Deficit': '{:.1f}'
                }), use_container_width=True, hide_index=True)
        else:
            st.warning("No data found for the selected filters.")

    except KeyError as e:
        st.error(f"Mapping Error: Could not find {e}. Please check your CSV headers.")
    except Exception as e:
        st.error(f"General Error: {e}")

else:
    st.info("Upload Mercury CSV to activate calculations.")
