import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Global Performance Engine", layout="wide")

st.title("📊 Global Performance & Efficiency Engine")
st.markdown("### Cross-Site Task Benchmarking & Load Balancing")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuration")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

qas_per_site = st.sidebar.number_input("Total QAs per Site", min_value=1, value=10)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file)
    
    # 1. SMART COLUMN DETECTION
    def find_col(keywords, df_cols):
        for k in keywords:
            for col in df_cols:
                if k.lower() in col.lower(): return col
        return None

    col_site = find_col(["Column-1", "Site"], raw_df.columns)
    col_locale = find_col(["Column-2", "Locale"], raw_df.columns)
    col_wf = find_col(["Column-4", "Transformation Type"], raw_df.columns)
    col_aht = find_col(["Average Handle Time", "AHT"], raw_df.columns)
    col_units = find_col(["Processed Units", "Processed"], raw_df.columns)

    if not all([col_site, col_wf, col_aht, col_units]):
        st.error("Missing columns! Please check your CSV headers.")
        st.stop()

    # Create Clean DF
    df = raw_df[[col_site, col_locale, col_wf, col_aht, col_units]].copy()
    df.columns = ['site', 'locale', 'workflow', 'aht', 'units']
    
    # Numeric Cleanup
    df['aht'] = pd.to_numeric(df['aht'], errors='coerce')
    df['units'] = pd.to_numeric(df['units'], errors='coerce')
    df = df.dropna(subset=['aht', 'units'])

    # 2. CALCULATION ENGINE (Trimmed Mean)
    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    # Actual AHT per Site/Workflow
    site_wf_performance = df.groupby(['site', 'workflow'])['aht'].apply(get_trimmed_mean).reset_index()
    network_goals = df.groupby('workflow')['aht'].apply(get_trimmed_mean).to_dict()

    # 3. GLOBAL CAPACITY SUMMARY
    site_stats = []
    for site in df['site'].unique():
        s_df = df[df['site'] == site]
        total_work_hours = 0
        total_units = s_df['units'].sum()

        for wf in s_df['workflow'].unique():
            actual_aht = site_wf_performance[(site_wf_performance['site'] == site) & (site_wf_performance['workflow'] == wf)]['aht'].values[0]
            units = s_df[s_df['workflow'] == wf]['units'].sum()
            total_work_hours += (units * actual_aht) / 3600

        capacity = qas_per_site * prod_hours * 5
        utilization = (total_work_hours / capacity) * 100
        
        site_stats.append({
            "Site": site,
            "Units": int(total_units),
            "Utilization %": round(utilization, 1),
            "Spare Man-Days": round((capacity - total_work_hours) / prod_hours, 1)
        })

    # --- UI LAYOUT ---
    st.subheader("🌐 Global Site Comparison")
    summary_df = pd.DataFrame(site_stats)
    st.dataframe(summary_df, use_container_width=True)

    st.divider()

    # --- TASK COMPARISON VIEW ---
    st.subheader("🔍 Workflow Deep-Dive (Task Comparison)")
    target_wf = st.selectbox("Select Workflow to Compare across Sites:", df['workflow'].unique())

    wf_comparison = site_wf_performance[site_wf_performance['workflow'] == target_wf]
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.write(f"**AHT Comparison for {target_wf}**")
        # Using Streamlit's native bar chart (No Matplotlib needed!)
        st.bar_chart(wf_comparison.set_index('site')['aht'])
    with col_b:
        st.write("**Performance Data**")
        st.table(wf_comparison[['site', 'aht']].rename(columns={'aht': 'Cleaned AHT (s)'}))

else:
    st.info("Upload your Mercury CSV to see the Global Efficiency Dashboard.")
