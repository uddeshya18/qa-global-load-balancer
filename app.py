import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Dynamic Global Forecast", layout="wide")

st.title("🔮 Dynamic Global Performance & Forecast")
st.markdown(f"### Reporting Date: **{datetime.now().strftime('%B %d, 2026')}**")

# --- SIDEBAR: GLOBAL CONTROLS ---
st.sidebar.header("⚙️ Global Settings")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

# Hover Definitions (Generic Definitions as requested)
hc_def = "Headcount (HC) Needed: The number of full-time employees required to complete the predicted volume based on historical speed."
aht_def = "Cleaned AHT: The 95th Percentile Trimmed Mean. It removes the slowest 5% of tasks to filter out system glitches."
util_def = "Utilization %: How much of a team's total available hours will be consumed by the predicted workload."

qas_per_site = st.sidebar.number_input("Current QAs per Locale", min_value=1, value=10, help=hc_def)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5, help="Actual time spent working per day.")
growth_buffer = st.sidebar.slider("Expected Growth (%)", 0, 100, 10, help="Anticipated volume increase for the future.")

# --- DYNAMIC DATE CALCULATIONS ---
current_date = datetime.now()
prediction_end = current_date + timedelta(weeks=4)
WEEKS_IN_DATA = 11  # Total weeks from Jan 1 to Mar 18

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
    selected_wf = st.sidebar.selectbox("Filter by Workflow:", ["All Workflows"] + sorted(df['workflow'].unique()))

    mask = (df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))
    if selected_wf != "All Workflows": mask = mask & (df['workflow'] == selected_wf)
    f_df = df[mask]

    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    if f_df.empty:
        st.warning("⚠️ No data selected.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Future Prediction"])

        with tab1:
            lookback_choice = st.radio("Historical Timeframe:", ["Full Data (Jan 1 - Mar 18)", "Last 4 Weeks of Data"], horizontal=True)
            weeks_divisor = 11 if "Full" in lookback_choice else 4
            
            st.subheader(f"Historical Performance ({lookback_choice})")
            
            # Aggregation
            summary_loc = f_df.groupby('locale').agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            if "Last 4 Weeks" in lookback_choice:
                # We simulate the 'last 4 weeks' by taking 4/11ths of the total volume for the audit
                summary_loc['units'] = (summary_loc['units'] * (4/11))
            
            summary_loc['Weekly Units'] = (summary_loc['units'] / weeks_divisor).astype(int)
            st.dataframe(summary_loc.rename(columns={'aht': 'Cleaned AHT (s)'}), use_container_width=True)
            
            st.write("### 🛠️ Workflow Level Audit")
            hist_wf = f_df.groupby(['locale', 'workflow']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            st.dataframe(hist_wf, use_container_width=True)

        with tab2:
            st.subheader(f"Prediction: {current_date.strftime('%d %b')} to {prediction_end.strftime('%d %b %Y')}")
            st.info(f"💡 {hc_def}")
            
            forecast_results = []
            for loc in f_df['locale'].unique():
                loc_data = f_df[f_df['locale'] == loc]
                curr_weekly = loc_data['units'].sum() / 11 # Baseline run-rate
                pred_weekly = curr_weekly * (1 + (growth_buffer / 100))
                aht_val = get_trimmed_mean(loc_data['aht'])
                req_hours = (pred_weekly * aht_val) / 3600
                hc_needed = req_hours / (prod_hours * 5)
                
                forecast_results.append({
                    "Locale": loc,
                    "Predicted Units/Week": int(pred_weekly),
                    "Utilization %": round((req_hours / (qas_per_site * prod_hours * 5)) * 100, 1),
                    "HC Needed": round(hc_needed, 1),
                    "Surplus/Deficit": round(qas_per_site - hc_needed, 1)
                })

            f_res_df = pd.DataFrame(forecast_results)
            st.dataframe(f_res_df.style.applymap(lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', subset=['Surplus/Deficit']), use_container_width=True)

            # --- DYNAMIC ACTION PLAN ---
            st.divider()
            st.subheader("📢 Executive Action Plan")
            total_hc_deficit = f_res_df[f_res_df['Surplus/Deficit'] < 0]['Surplus/Deficit'].sum()
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.error("### 🚨 Risks")
                st.write(f"* **Staffing:** Predicted shortfall of **{abs(total_hc_deficit):.1f} people** by {prediction_end.strftime('%d %b')}.")
            with col_b:
                st.success("### ✅ Opportunities")
                total_surplus = f_res_df[f_res_df['Surplus/Deficit'] > 0]['Surplus/Deficit'].sum()
                st.write(f"* **Mobility:** **{total_surplus:.1f} HC** can be moved to cover deficits.")

else:
    st.info("Upload CSV to initialize the Dynamic Forecast Engine.")
