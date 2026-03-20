import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Dynamic Global Forecast", layout="wide")

st.title("🔮 Dynamic Global Performance & Forecast")
st.markdown(f"### Current Date: **{datetime.now().strftime('%B %d, %y')}** | 4-Week Strategic Projection")

# --- SIDEBAR: GLOBAL CONTROLS ---
st.sidebar.header("⚙️ Global Settings")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

qas_per_site = st.sidebar.number_input(
    "Current QAs (per selected locale)", 
    min_value=1, value=10, 
    help="The total number of full-time QA resources currently assigned to the selected locale."
)
prod_hours = st.sidebar.slider(
    "Daily Productive Hours", 5.0, 9.0, 7.5,
    help="Actual time spent on tasks, excluding breaks, meetings, and training."
)
growth_buffer = st.sidebar.slider(
    "Expected Growth (%)", 0, 100, 10,
    help="The anticipated percentage increase in task volume for the next 4 weeks."
)

# --- DYNAMIC DATE CALCULATIONS ---
current_date = datetime.now()
forecast_end_date = current_date + timedelta(weeks=4)
# Historical data period (Jan 1 to Mar 18 = ~11 weeks)
WEEKS_IN_DATA = 11 

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
    sites = sorted(df['site'].unique())
    selected_sites = st.sidebar.multiselect("Filter by Site:", sites, default=sites)
    locales = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
    selected_locales = st.sidebar.multiselect("Filter by Locale:", locales, default=locales)
    workflows = sorted(df[df['locale'].isin(selected_locales)]['workflow'].unique())
    selected_wf = st.sidebar.selectbox("Filter by Workflow:", ["All Workflows"] + workflows)

    mask = (df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))
    if selected_wf != "All Workflows":
        mask = mask & (df['workflow'] == selected_wf)
    
    f_df = df[mask]

    # Cleaned AHT Definition for Tooltips
    aht_help = "95th Percentile Trimmed Mean: Removes the slowest 5% of tasks to eliminate technical glitches and noise."

    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    if f_df.empty:
        st.warning("⚠️ **No data selected.** Please adjust filters.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical Review", "🚀 Forecast & Capacity"])

        with tab1:
            st.subheader(f"Q1 Performance Audit (Reference Period: {WEEKS_IN_DATA} Weeks)")
            summary_loc = f_df.groupby('locale').agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            st.dataframe(summary_loc.rename(columns={'aht': 'Cleaned AHT (s)'}), use_container_width=True)
            
            st.write("### 🛠️ Workflow Level Statistics")
            hist_wf = f_df.groupby(['locale', 'workflow']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            st.dataframe(hist_wf, use_container_width=True)

        with tab2:
            st.subheader(f"Next 4-Week Projection: {current_date.strftime('%d %b')} — {forecast_end_date.strftime('%d %b %Y')}")
            
            forecast_results = []
            for loc in f_df['locale'].unique():
                loc_data = f_df[f_df['locale'] == loc]
                curr_weekly = loc_data['units'].sum() / WEEKS_IN_DATA
                pred_weekly = curr_weekly * (1 + (growth_buffer / 100))
                aht_val = get_trimmed_mean(loc_data['aht'])
                req_hours = (pred_weekly * aht_val) / 3600
                hc_needed = req_hours / (prod_hours * 5)
                
                forecast_results.append({
                    "Locale": loc,
                    "Predicted Units/Week": int(pred_weekly),
                    "Utilization %": round((req_hours / (qas_per_site * prod_hours * 5)) * 100, 1),
                    "HC Needed": round(hc_needed, 1),
                    "Surplus/Deficit": round(qas_per_site - hc_needed, 1),
                    "Total Req. Hours": round(req_hours, 1)
                })

            f_res_df = pd.DataFrame(forecast_results)
            st.write("**Forecast Summary by Locale**", help="HC Needed = (Total Time Required / Weekly Productive Hours per person). Surplus/Deficit shows how many people to move or hire.")
            st.dataframe(f_res_df.style.applymap(lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', subset=['Surplus/Deficit']), use_container_width=True)

            # --- DYNAMIC ACTION PLAN ---
            st.divider()
            st.subheader("📢 Executive Action Plan")
            
            total_hc_deficit = f_res_df[f_res_df['Surplus/Deficit'] < 0]['Surplus/Deficit'].sum()
            highest_util = f_res_df.loc[f_res_df['Utilization %'].idxmax()]
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.error("### 🚨 Critical Risks")
                if total_hc_deficit < 0:
                    st.write(f"* **Staffing Shortfall:** From now until **{forecast_end_date.strftime('%d %b')}**, you are short by **{abs(total_hc_deficit):.1f} people**.")
                st.write(f"* **Bottle-neck Locale:** **{highest_util['Locale']}** will hit **{highest_util['Utilization %']}%** capacity based on historical performance.")

            with col_b:
                st.success("### ✅ Opportunities")
                total_surplus = f_res_df[f_res_df['Surplus/Deficit'] > 0]['Surplus/Deficit'].sum()
                st.write(f"* **Internal Mobility:** You have **{total_surplus:.1f} HC** available to reallocate from surplus sites to deficit sites.")
                st.write(f"* **Planning Window:** You have 4 weeks to adjust volume before the projected peak on **{forecast_end_date.strftime('%d %b')}**.")

else:
    st.info("Upload CSV to generate your dynamic 4-week forecast.")
