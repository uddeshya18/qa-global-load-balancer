import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Global Performance & Forecast", layout="wide")

st.title("🔮 Global Performance & Forecast Engine")
st.markdown("### Historical Analysis (Jan-Mar) & April Capacity Projection")

# --- SIDEBAR: GLOBAL CONTROLS & FILTERS ---
st.sidebar.header("⚙️ Global Settings")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

# Global variables for the math
qas_per_site = st.sidebar.number_input("Current QAs (per selected locale)", min_value=1, value=10)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
growth_buffer = st.sidebar.slider("Expected Growth (%)", 0, 100, 10)

WEEKS_IN_DATA = 11 # Jan 1 - March 18

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

    # Data Cleaning
    df = raw_df[[col_site, col_loc, col_wf, col_aht, col_units]].copy()
    df.columns = ['site', 'locale', 'workflow', 'aht', 'units']
    df['aht'] = pd.to_numeric(df['aht'], errors='coerce')
    df['units'] = pd.to_numeric(df['units'], errors='coerce')
    df = df.dropna(subset=['aht', 'units'])

    # 2. DYNAMIC FILTERS (The Drill-Down)
    st.sidebar.divider()
    st.sidebar.subheader("🔍 Filter Data")
    
    # Site Filter
    sites = sorted(df['site'].unique())
    selected_sites = st.sidebar.multiselect("Filter by Site:", sites, default=sites)
    
    # Locale Filter (Dependent on Site)
    locales = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
    selected_locales = st.sidebar.multiselect("Filter by Locale:", locales, default=locales)
    
    # Workflow Filter (Dependent on Locale)
    workflows = sorted(df[df['locale'].isin(selected_locales)]['workflow'].unique())
    selected_wf = st.sidebar.selectbox("Filter by Workflow:", ["All Workflows"] + workflows)

    # Applying the Filters
    mask = (df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))
    if selected_wf != "All Workflows":
        mask = mask & (df['workflow'] == selected_wf)
    
    f_df = df[mask]

    # 3. CALCULATION ENGINE
    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    # --- SAFETY GATE: CHECK IF DATA IS SELECTED ---
    if f_df.empty:
        st.warning("⚠️ **No data selected.** Please select at least one Site and Locale in the sidebar to view the analysis.")
    else:
        # --- TABBED INTERFACE ---
        tab1, tab2 = st.tabs(["📊 Historical Review", "🚀 Forecast & Capacity"])

        with tab1:
            st.subheader("Historical Performance Metrics")
            
            # Site Summary aggregation
            summary = f_df.groupby('locale').agg({
                'units': 'sum',
                'aht': get_trimmed_mean
            }).reset_index()
            
            summary['Weekly Units'] = (summary['units'] / WEEKS_IN_DATA).astype(int)
            summary = summary.rename(columns={'aht': 'Cleaned AHT (s)', 'units': 'Total Units'})

            c1, c2, c3 = st.columns(3)
            c1.metric("Selected Units", f"{int(summary['Total Units'].sum()):,}")
            c2.metric("Avg Weekly Vol", f"{int(summary['Weekly Units'].sum()):,}")
            c3.metric("Trimmed AHT", f"{summary['Cleaned AHT (s)'].mean():.1f}s")

            st.divider()
            st.write("**Performance by Locale**")
            st.dataframe(summary[['locale', 'Total Units', 'Weekly Units', 'Cleaned AHT (s)']], use_container_width=True)
            st.bar_chart(summary.set_index('locale')['Weekly Units'])

        with tab2:
            st.subheader("Future Capacity Forecaster")
            st.write(f"Projecting load for the next 4 weeks (Assuming {growth_buffer}% Growth)")
            
            forecast_results = []
            for loc in f_df['locale'].unique():
                loc_data = f_df[f_df['locale'] == loc]
                
                # Math
                curr_weekly = loc_data['units'].sum() / WEEKS_IN_DATA
                pred_weekly = curr_weekly * (1 + (growth_buffer / 100))
                aht_val = get_trimmed_mean(loc_data['aht'])
                
                req_hours = (pred_weekly * aht_val) / 3600
                avail_hours = qas_per_site * prod_hours * 5
                util_pct = (req_hours / avail_hours) * 100
                hc_needed = req_hours / (prod_hours * 5)
                
                forecast_results.append({
                    "Locale": loc,
                    "Predicted Units/Week": int(pred_weekly),
                    "Utilization %": round(util_pct, 1),
                    "HC Needed": round(hc_needed, 1),
                    "Current HC": qas_per_site,
                    "Surplus/Deficit": round(qas_per_site - hc_needed, 1)
                })

            f_results_df = pd.DataFrame(forecast_results)
            
            # --- FINAL SAFETY CHECK BEFORE STYLING ---
            if not f_results_df.empty:
                def color_deficit(val):
                    return 'background-color: #ffcccc' if val < 0 else 'background-color: #ccffcc'
                
                # Render styled dataframe
                st.dataframe(
                    f_results_df.style.applymap(color_deficit, subset=['Surplus/Deficit']), 
                    use_container_width=True
                )
                
                st.warning("⚠️ **Note:** Red cells in 'Surplus/Deficit' indicate locales where current headcount cannot meet the predicted volume.")
            else:
                st.info("Insufficient data to generate a forecast for the current selection.")

else:
    st.info("Upload the Mercury CSV and use the sidebar filters to drill down into specific branches or locales.")
