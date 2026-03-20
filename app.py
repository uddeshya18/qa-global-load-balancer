import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Strategic Planner", layout="wide")

st.title("🔮 Strategic Capacity Planner & Stress Test")
st.markdown(f"### Reporting Date: **{datetime.now().strftime('%A, %b %d, 2026')}**")

# --- SIDEBAR: GLOBAL CONTROLS ---
st.sidebar.header("⚙️ Global Settings")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

# Hover Definitions
hc_def = "Headcount (HC) Needed: People required to finish the volume based on chosen scenario."
aht_def = "Cleaned AHT: 95th Percentile Trimmed Mean (removes 5% slowest glitches)."
stress_def = "Scenario Planning: 'Worst Case' uses a higher AHT (slower team) to see if we can still survive a bad week."

qas_per_site = st.sidebar.number_input("Current QAs per Locale", min_value=1, value=10, help=hc_def)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
growth_per_week = st.sidebar.slider("Weekly Volume Growth (%)", 0, 20, 5)

# --- NEW: SCENARIO SELECTOR ---
st.sidebar.divider()
st.sidebar.subheader("⚖️ Scenario Stress Test")
scenario = st.sidebar.radio(
    "Select Performance Scenario:",
    ["Base Case (Current Avg)", "Best Case (Peak Speed)", "Worst Case (Slower AHT)"],
    help=stress_def
)

# --- DYNAMIC MONDAY-FRIDAY DATE LOGIC ---
def get_next_monday(d):
    days_ahead = 0 - d.weekday()
    if days_ahead <= 0: days_ahead += 7
    return d + timedelta(days_ahead)

start_of_week_1 = get_next_monday(datetime.now())

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file)
    
    # Column Detection
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

    # Scenario Multiplier Logic
    # Best Case assumes team is 10% faster; Worst Case assumes 15% slower (extra complexity)
    aht_multiplier = 1.0
    if "Best Case" in scenario: aht_multiplier = 0.90
    if "Worst Case" in scenario: aht_multiplier = 1.15

    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    if df.empty:
        st.warning("⚠️ No data found.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Weekly Prediction"])

        with tab1:
            st.subheader("Historical Performance (Jan 1 - Mar 18)")
            summary_loc = df.groupby('locale').agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            summary_loc['Avg Weekly Units'] = (summary_loc['units'] / 11).astype(int)
            st.dataframe(summary_loc.rename(columns={'aht': 'Cleaned AHT (s)'}), use_container_width=True)

        with tab2:
            st.subheader(f"Forecast Horizon ({scenario})")
            
            # --- WEEK SELECTOR ---
            week_options = []
            for i in range(1, 5):
                m_date = start_of_week_1 + timedelta(weeks=i-1)
                f_date = m_date + timedelta(days=4)
                week_options.append(f"Week {i}: {m_date.strftime('%d %b')} to {f_date.strftime('%d %b')}")
            
            selected_week_str = st.selectbox("Select Forecast Week:", week_options)
            week_idx = int(selected_week_str.split(":")[0].split(" ")[1])
            
            st.info(f"💡 Performance Scenario: **{scenario}** (AHT Adjusted by {int((aht_multiplier-1)*100)}%)")
            
            # Calculations
            week_results = []
            wf_details = []
            for loc in df['locale'].unique():
                loc_data = df[df['locale'] == loc]
                base_weekly = loc_data['units'].sum() / 11
                growth_factor = (1 + (growth_per_week / 100)) ** week_idx
                pred_vol = base_weekly * growth_factor
                
                # Apply Scenario Multiplier to AHT
                aht_val = get_trimmed_mean(loc_data['aht']) * aht_multiplier
                
                req_hours = (pred_vol * aht_val) / 3600
                hc_needed = req_hours / (prod_hours * 5)
                
                week_results.append({
                    "Locale": loc,
                    "Total Exp. Volume": int(pred_vol),
                    "Utilization %": round((req_hours / (qas_per_site * prod_hours * 5)) * 100, 1),
                    "HC Needed": round(hc_needed, 1),
                    "Surplus/Deficit": round(qas_per_site - hc_needed, 1)
                })

                # Detailed WF breakdown
                wf_group = loc_data.groupby('workflow').agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
                for _, row in wf_group.iterrows():
                    wf_pred = (row['units'] / 11) * growth_factor
                    wf_aht = row['aht'] * aht_multiplier
                    wf_details.append({
                        "Locale": loc,
                        "Transformation Type": row['workflow'],
                        "Exp. Units": int(wf_pred),
                        "Req. Prod Hours": round((wf_pred * wf_aht) / 3600, 1)
                    })

            st.write("### 📍 Locale Staffing Status")
            st.dataframe(pd.DataFrame(week_results).style.applymap(lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', subset=['Surplus/Deficit']), use_container_width=True)
            
            st.write("### 🛠️ Workflow Level Requirement")
            st.dataframe(pd.DataFrame(wf_details).sort_values(['Locale', 'Req. Prod Hours'], ascending=[True, False]), use_container_width=True)

else:
    st.info("Upload CSV to enable Stress Testing.")
