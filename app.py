import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Global Predictor Engine", layout="wide")

st.title("🔮 Global Performance & Forecast Engine")
st.markdown("### Historical Analysis (Jan-Mar) & Automated Action Plan")

# --- SIDEBAR: GLOBAL CONTROLS & FILTERS ---
st.sidebar.header("⚙️ Global Settings")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

qas_per_site = st.sidebar.number_input("Current QAs (per selected locale)", min_value=1, value=10)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
growth_buffer = st.sidebar.slider("Expected Growth (%)", 0, 100, 10)

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

    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    if f_df.empty:
        st.warning("⚠️ **No data selected.** Please adjust filters.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical Review", "🚀 Forecast & Capacity"])

        with tab1:
            st.subheader("Q1 Performance Audit")
            summary_loc = f_df.groupby('locale').agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            st.dataframe(summary_loc.rename(columns={'aht': 'Cleaned AHT (s)'}), use_container_width=True)
            st.write("### 🛠️ Historical Workflow Breakdown")
            hist_wf = f_df.groupby(['locale', 'workflow']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            st.dataframe(hist_wf, use_container_width=True)

        with tab2:
            st.subheader("Future Capacity Forecaster")
            
            # --- CALCULATE FORECASTS ---
            forecast_results = []
            wf_details = []
            
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
            st.dataframe(f_res_df.style.applymap(lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', subset=['Surplus/Deficit']), use_container_width=True)

            # --- DYNAMIC MANAGEMENT SUMMARY (The Final Polish) ---
            st.divider()
            st.subheader("📢 Executive Action Plan")
            
            total_hc_deficit = f_res_df[f_res_df['Surplus/Deficit'] < 0]['Surplus/Deficit'].sum()
            total_hc_surplus = f_res_df[f_res_df['Surplus/Deficit'] > 0]['Surplus/Deficit'].sum()
            highest_util = f_res_df.loc[f_res_df['Utilization %'].idxmax()]
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.error("### 🚨 Critical Risks")
                if total_hc_deficit < 0:
                    st.write(f"* **Staffing Shortfall:** Across selected locales, you are short by **{abs(total_hc_deficit):.1f} HC**. You need to hire or reallocate immediately.")
                st.write(f"* **Primary Bottleneck:** **{highest_util['Locale']}** is at **{highest_util['Utilization %']}%** capacity. Any further volume growth here will lead to immediate SLA failure.")
                
                # Find most time-consuming workflow
                wf_sum = f_df.groupby('workflow').agg({'units': 'sum', 'aht': get_trimmed_mean})
                wf_sum['Hours'] = (wf_sum['units'] / WEEKS_IN_DATA * (1 + growth_buffer/100) * wf_sum['aht']) / 3600
                heavy_wf = wf_sum['Hours'].idxmax()
                st.write(f"* **Heaviest Workflow:** **{heavy_wf}** requires the most manual effort (**{wf_sum['Hours'].max():.1f} hours/week**). Focus optimization efforts here.")

            with col_b:
                st.success("### ✅ Opportunities")
                if total_hc_surplus > 0:
                    st.write(f"* **Available Capacity:** You have a surplus of **{total_hc_surplus:.1f} HC** across certain nodes. These resources can be shifted to cover deficits.")
                
                # Finding the most efficient locale (lowest AHT)
                best_loc = summary_loc.loc[summary_loc['aht'].idxmin()]
                st.write(f"* **Efficiency Leader:** **{best_loc['locale']}** has the best AHT (**{best_loc['aht']:.1f}s**). Consider using this locale as the 'Center of Excellence' for training others.")

else:
    st.info("Upload the Mercury CSV to generate the historical audit and executive action plan.")
