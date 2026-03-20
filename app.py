import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Capacity Planner", layout="wide")

st.title("🔮 Strategic Capacity Planner (Mon-Fri)")
st.markdown(f"### Reporting Date: **{datetime.now().strftime('%A, %b %d, 2026')}**")

# --- SIDEBAR: GLOBAL CONTROLS ---
st.sidebar.header("⚙️ Global Settings")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

# Definitions for the Help Expander
definitions = {
    "HC Needed": "The number of full-time employees required for this specific week's volume.",
    "Cleaned AHT": "The 95th Percentile Trimmed Mean. Removes the slowest 5% of 'glitch' tasks.",
    "Productive Hours": "Actual hours spent processing (excluding breaks/meetings).",
    "Utilization %": "Percentage of available team hours consumed by work. >100% = Understaffed.",
    "Surplus/Deficit": "(+) means extra people; (-) means you need more people."
}

qas_per_site = st.sidebar.number_input("Current QAs per Locale", min_value=1, value=10)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
growth_per_week = st.sidebar.slider("Weekly Volume Growth (%)", 0, 20, 5)

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

    # Filters
    st.sidebar.divider()
    st.sidebar.subheader("🔍 Filter Data")
    selected_sites = st.sidebar.multiselect("Filter by Site:", sorted(df['site'].unique()), default=df['site'].unique())
    selected_locales = st.sidebar.multiselect("Filter by Locale:", sorted(df[df['site'].isin(selected_sites)]['locale'].unique()), default=df[df['site'].isin(selected_sites)]['locale'].unique())
    f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    if f_df.empty:
        st.warning("⚠️ No data selected.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Future Prediction"])

        with tab1:
            st.subheader("Historical Performance (Jan 1 - Mar 18)")
            summary_loc = f_df.groupby('locale').agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            summary_loc['Avg Weekly Units'] = (summary_loc['units'] / 11).astype(int)
            
            st.dataframe(summary_loc.rename(columns={'aht': 'Cleaned AHT (s)'}).style.format({'Cleaned AHT (s)': '{:.1f}'}), use_container_width=True)
            
            st.markdown("### 🛠️ Workflow Level Audit")
            hist_wf = f_df.groupby(['locale', 'workflow']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            st.dataframe(hist_wf.rename(columns={'aht': 'Cleaned AHT (s)'}).style.format({'Cleaned AHT (s)': '{:.1f}'}), use_container_width=True)

        with tab2:
            st.subheader("Weekly Forecast Explorer")
            
            # Use Expander for help instead of st.write(help=...) to prevent crash
            with st.expander("📖 Glossary & Definitions"):
                for term, val in definitions.items():
                    st.write(f"**{term}:** {val}")

            week_options = []
            for i in range(1, 5):
                m_date = start_of_week_1 + timedelta(weeks=i-1)
                f_date = m_date + timedelta(days=4)
                week_options.append(f"Week {i}: {m_date.strftime('%d %b')} to {f_date.strftime('%d %b')}")
            
            selected_week_str = st.selectbox("Select Forecast Week:", week_options)
            week_idx = int(selected_week_str.split(":")[0].split(" ")[1])
            
            st.info(f"💡 Predictions for **{selected_week_str}**. (Mon-Fri)")
            
            # Calculations
            week_results = []
            wf_details = []
            
            for loc in f_df['locale'].unique():
                loc_data = f_df[f_df['locale'] == loc]
                base_weekly = loc_data['units'].sum() / 11
                growth_factor = (1 + (growth_per_week / 100)) ** week_idx
                pred_vol = base_weekly * growth_factor
                aht_val = get_trimmed_mean(loc_data['aht'])
                req_hours = (pred_vol * aht_val) / 3600
                hc_needed = req_hours / (prod_hours * 5)
                
                week_results.append({
                    "Locale": loc,
                    "Total Exp. Volume": int(pred_vol),
                    "Utilization %": (req_hours / (qas_per_site * prod_hours * 5)) * 100,
                    "HC Needed": hc_needed,
                    "Surplus/Deficit": qas_per_site - hc_needed
                })

            wf_group = f_df.groupby(['locale', 'workflow']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            for _, row in wf_group.iterrows():
                base_wf_vol = row['units'] / 11
                pred_wf_vol = base_wf_vol * ((1 + (growth_per_week / 100)) ** week_idx)
                req_hrs_wf = (pred_wf_vol * row['aht']) / 3600
                wf_details.append({
                    "Locale": row['locale'],
                    "Transformation Type": row['workflow'],
                    "Exp. Units": int(pred_wf_vol),
                    "Req. Prod Hours": req_hrs_wf
                })

            # Formatting
            st.markdown("### 📍 Locale Staffing Status")
            res_df = pd.DataFrame(week_results)
            st.dataframe(
                res_df.style.map(lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', subset=['Surplus/Deficit'])
                .format({'Utilization %': '{:.1f}%', 'HC Needed': '{:.1f}', 'Surplus/Deficit': '{:.1f}'}), 
                use_container_width=True
            )
            
            st.markdown("### 🛠️ Transformation Type Breakdown")
            wf_df = pd.DataFrame(wf_details)
            st.dataframe(
                wf_df.sort_values(['Locale', 'Req. Prod Hours'], ascending=[True, False])
                .style.format({'Req. Prod Hours': '{:.1f}'}), 
                use_container_width=True
            )

else:
    st.info("Upload Mercury CSV to activate the Dynamic Planner.")
