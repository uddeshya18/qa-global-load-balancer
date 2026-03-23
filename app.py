import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Strategic Capacity Planner", layout="wide")

st.title("📊 Strategic Capacity Planner (Position-Based)")
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
    # 1. READ DATA (Using sep=None to auto-detect delimiters like commas or semicolons)
    raw_df = pd.read_csv(uploaded_file, sep=None, engine='python')
    
    # 2. POSITION-BASED MAPPING (Based on your screenshot)
    # This ignores the header names and just looks at where the data sits.
    try:
        # We find columns by their index position to avoid "Mapping Errors"
        # Column-1 is index 0, Column-2 is index 1, etc.
        df = pd.DataFrame()
        df['site'] = raw_df.iloc[:, 0].astype(str).str.strip().str.upper() # Column-1
        df['locale'] = raw_df.iloc[:, 1].astype(str).str.strip()           # Column-2
        df['workflow'] = raw_df.iloc[:, 3].astype(str).str.strip()         # Column-4
        
        # Finding numerical columns by searching for keywords in the header list
        cols = list(raw_df.columns)
        
        def get_col_by_name(search_term):
            for i, col in enumerate(cols):
                if search_term.lower() in str(col).lower(): return i
            return None

        idx_date = get_col_by_name("Date Part") or 9  # Usually Column-10
        idx_units = get_col_by_name("Processed Units") or 13 
        idx_aht = get_col_by_name("Handle Time") or 16

        df['date_str'] = raw_df.iloc[:, idx_date].astype(str)
        df['units'] = pd.to_numeric(raw_df.iloc[:, idx_units], errors='coerce').fillna(0)
        df['aht'] = pd.to_numeric(raw_df.iloc[:, idx_aht], errors='coerce').fillna(0)

        # 3. BASELINE CALCULATIONS
        unique_weeks = df['date_str'].unique()
        num_weeks = len(unique_weeks) if len(unique_weeks) > 0 else 1

        # Calculate Historical Growth
        growth_map = {}
        weekly_trend = df.groupby(['locale', 'date_str'])['units'].sum().reset_index()
        for loc in weekly_trend['locale'].unique():
            loc_trend = weekly_trend[weekly_trend['locale'] == loc]
            if len(loc_trend) > 1:
                first = loc_trend.iloc[0]['units']
                last = loc_trend.iloc[-1]['units']
                rate = ((last / first) ** (1 / len(loc_trend))) - 1 if first > 0 else 0
                growth_map[loc] = max(0, rate * 100)
            else: growth_map[loc] = 0

        avg_historical_growth = sum(growth_map.values()) / len(growth_map) if growth_map else 0
        
        st.sidebar.divider()
        st.sidebar.info(f"📈 Detected Growth Trend: **{avg_historical_growth:.1f}%**")
        growth_per_week = st.sidebar.slider("Apply Future Growth (%)", 0, 20, int(avg_historical_growth))

        # 4. FILTERS
        selected_sites = st.sidebar.multiselect("Filter Site:", sorted(df['site'].unique()), default=df['site'].unique())
        available_locales = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
        selected_locales = st.sidebar.multiselect("Filter Locale:", available_locales, default=available_locales)
        
        f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

        if not f_df.empty:
            tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Future Prediction"])
            
            def get_trimmed_mean(group):
                if len(group) < 3: return group.median()
                return group[group <= group.quantile(0.95)].mean()

            with tab1:
                st.subheader("Historical Performance")
                summary_loc = f_df.groupby('locale').agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
                summary_loc['Avg Weekly Units'] = (summary_loc['units'] / num_weeks).astype(int)
                summary_loc['Observed Growth %'] = summary_loc['locale'].map(growth_map)
                st.dataframe(summary_loc.style.format({'aht': '{:.1f}', 'Observed Growth %': '{:.1f}%'}), use_container_width=True, hide_index=True)

            with tab2:
                week_idx = int(st.selectbox("Select Forecast Week:", [1, 2, 3, 4]))
                week_results = []
                for loc in f_df['locale'].unique():
                    loc_data = f_df[f_df['locale'] == loc]
                    base_weekly = loc_data['units'].sum() / num_weeks
                    pred_vol = base_weekly * ((1 + (growth_per_week / 100)) ** week_idx)
                    aht_val = get_trimmed_mean(loc_data['aht'])
                    req_hours = (pred_vol * aht_val) / 3600
                    hc_needed = req_hours / (prod_hours * 5)
                    
                    week_results.append({
                        "Locale": loc, "Exp. Volume": int(pred_vol),
                        "Utilization %": (req_hours / (qas_per_site * prod_hours * 5)) * 100 if qas_per_site > 0 else 0,
                        "HC Needed": hc_needed, "Surplus/Deficit": qas_per_site - hc_needed
                    })
                st.dataframe(pd.DataFrame(week_results).style.format({'Utilization %': '{:.1f}%', 'HC Needed': '{:.1f}', 'Surplus/Deficit': '{:.1f}'}), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Critical Error: {e}")
        st.write("Ensure your CSV has at least 17 columns as per the Mercury standard.")
else:
    st.info("Upload Mercury CSV to activate.")
