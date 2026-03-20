import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Global Predictor Engine", layout="wide")

st.title("🔮 Global Performance & Forecast Engine")
st.markdown("### Historical Analysis (Jan-Mar) & Workflow-Level Projection")

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

    # --- SAFETY GATE ---
    if f_df.empty:
        st.warning("⚠️ **No data selected.** Please select a Site and Locale in the sidebar.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical Review", "🚀 Forecast & Capacity"])

        with tab1:
            st.subheader("Q1 Performance Audit (Jan 1 - Mar 18)")
            
            # Key Metrics Header
            summary_loc = f_df.groupby('locale').agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            total_units = summary_loc['units'].sum()
            avg_network_aht = summary_loc['aht'].mean()

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Q1 Units", f"{int(total_units):,}")
            c2.metric("Weekly Avg Velocity", f"{int(total_units/WEEKS_IN_DATA):,}")
            c3.metric("Network Cleaned AHT", f"{avg_network_aht:.1f}s")

            st.divider()
            
            # NEW: Granular Workflow Table in Historical Tab
            st.write("### 🛠️ Historical Volume by Transformation Type")
            hist_wf = f_df.groupby(['locale', 'workflow']).agg({
                'units': 'sum',
                'aht': get_trimmed_mean
            }).reset_index()
            
            hist_wf['Weekly Units'] = (hist_wf['units'] / WEEKS_IN_DATA).astype(int)
            hist_wf = hist_wf.rename(columns={'aht': 'Cleaned AHT (s)', 'units': 'Total Q1 Units'})
            
            st.dataframe(hist_wf.sort_values(['locale', 'Total Q1 Units'], ascending=[True, False]), use_container_width=True)
            
            st.write("### 📈 Locale Throughput (Weekly)")
            st.bar_chart(summary_loc.set_index('locale')['units'] / WEEKS_IN_DATA)

        with tab2:
            st.subheader("Future Capacity Forecaster")
            st.write(f"Projecting load for the next 4 weeks (Assuming {growth_buffer}% Growth)")
            
            # LOCALE SUMMARY
            st.write("### 📍 Summary by Locale")
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
                    "Surplus/Deficit": round(qas_per_site - hc_needed, 1)
                })

            f_res_df = pd.DataFrame(forecast_results)
            def color_deficit(val):
                return 'background-color: #ffcccc' if val < 0 else 'background-color: #ccffcc'
            
            st.dataframe(f_res_df.style.applymap(color_deficit, subset=['Surplus/Deficit']), use_container_width=True)

            # WORKFLOW DETAIL
            st.divider()
            st.write("### 🛠️ Detail per Transformation Type")
            wf_details = []
            wf_group = f_df.groupby(['locale', 'workflow']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            for _, row in wf_group.iterrows():
                pred_vol = (row['units'] / WEEKS_IN_DATA) * (1 + (growth_buffer / 100))
                req_hrs = (pred_vol * row['aht']) / 3600
                wf_details.append({
                    "Locale": row['locale'],
                    "Workflow": row['workflow'],
                    "Cleaned AHT": round(row['aht'], 1),
                    "Pred. Units/Week": int(pred_vol),
                    "Req. Prod Hours": round(req_hrs, 1)
                })
            st.dataframe(pd.DataFrame(wf_details).sort_values(['Locale', 'Req. Prod Hours'], ascending=[True, False]), use_container_width=True)

else:
    st.info("Upload the Mercury CSV and use the sidebar filters to drill down.")
