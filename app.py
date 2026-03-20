import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- PAGE CONFIG ---
st.set_page_config(page_title="Global Performance Engine", layout="wide")

st.title("📊 Global Performance & Efficiency Engine")
st.markdown("### Complexity-Adjusted Load Balancing & Cross-Site Benchmarking")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuration")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

qas_per_site = st.sidebar.number_input("Total QAs per Site", min_value=1, value=10)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file)
    
    # 1. SMART COLUMN DETECTION (Prevents KeyError)
    # We look for keywords since Mercury headers vary
    def find_col(keywords, df_cols):
        for k in keywords:
            for col in df_cols:
                if k.lower() in col.lower():
                    return col
        return None

    col_site = find_col(["Column-1", "Site"], raw_df.columns)
    col_locale = find_col(["Column-2", "Locale"], raw_df.columns)
    col_wf = find_col(["Column-4", "Transformation Type"], raw_df.columns)
    col_aht = find_col(["Average Handle Time", "AHT"], raw_df.columns)
    col_units = find_col(["Processed Units", "Processed"], raw_df.columns)

    if not all([col_site, col_wf, col_aht, col_units]):
        st.error(f"Missing columns! Found: Site({col_site}), WF({col_wf}), AHT({col_aht}), Units({col_units})")
        st.stop()

    # Create Clean DF
    df = raw_df[[col_site, col_locale, col_wf, col_aht, col_units]].copy()
    df.columns = ['site', 'locale', 'workflow', 'aht', 'units']
    
    # Numeric Cleanup
    df['aht'] = pd.to_numeric(df['aht'], errors='coerce')
    df['units'] = pd.to_numeric(df['units'], errors='coerce')
    df = df.dropna(subset=['aht', 'units'])
    df = df[df['units'] > 0]

    # 2. CALCULATION ENGINE (Trimmed Mean & Efficiency Index)
    # Group by Site and Workflow to get the baseline
    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    # Actual AHT per Site/Workflow
    site_wf_performance = df.groupby(['site', 'workflow'])['aht'].apply(get_trimmed_mean).reset_index()
    
    # "Network Average" (Ew) - The Goal for each workflow based on all sites
    network_goals = df.groupby('workflow')['aht'].apply(get_trimmed_mean).to_dict()

    # 3. GLOBAL CAPACITY SUMMARY
    site_stats = []
    for site in df['site'].unique():
        s_df = df[df['site'] == site]
        
        # Calculate Required Hours using Network Goals (Ew) vs Actual (Aw)
        # This tells us if the site is "Efficient" compared to the network
        total_work_hours = 0
        rs_sum = 0
        total_units = s_df['units'].sum()

        for wf in s_df['workflow'].unique():
            wf_df = s_df[s_df['workflow'] == wf]
            actual_aht = site_wf_performance[(site_wf_performance['site'] == site) & (site_wf_performance['workflow'] == wf)]['aht'].values[0]
            goal_aht = network_goals[wf]
            units = wf_df['units'].sum()
            
            # Rs Contribution: (Goal / Actual) * (Units / Total Units)
            rs_sum += (goal_aht / actual_aht) * (units / total_units)
            total_work_hours += (units * actual_aht) / 3600

        capacity = qas_per_site * prod_hours * 5
        utilization = (total_work_hours / capacity) * 100
        
        site_stats.append({
            "Site": site,
            "Units": int(total_units),
            "Efficiency (Rs%)": round(rs_sum * 100, 1),
            "Utilization%": round(utilization, 1),
            "Spare Man-Days": round((capacity - total_work_hours) / prod_hours, 1)
        })

    # --- UI LAYOUT ---
    st.subheader("🌐 Global Site Comparison")
    summary_df = pd.DataFrame(site_stats)
    st.dataframe(summary_df.style.background_gradient(subset=['Efficiency (Rs%)', 'Utilization%'], cmap='RdYlGn_r'))

    st.divider()

    # --- COMPARISON VIEW ---
    st.subheader("🔍 Workflow Deep-Dive (Cross-Site Comparison)")
    target_wf = st.selectbox("Select Workflow to Compare across Sites:", df['workflow'].unique())

    # Filter data for this workflow
    wf_comparison = site_wf_performance[site_wf_performance['workflow'] == target_wf].copy()
    wf_comparison['Network_Avg'] = network_goals[target_wf]
    wf_comparison['Vs_Network%'] = (network_goals[target_wf] / wf_comparison['aht']) * 100

    col_a, col_b = st.columns(2)
    with col_a:
        st.write(f"**AHT per Site for {target_wf}**")
        st.bar_chart(wf_comparison.set_index('site')['aht'])
    with col_b:
        st.write("**Performance vs. Network Average**")
        # 100% means they are exactly at network average speed
        st.dataframe(wf_comparison[['site', 'aht', 'Vs_Network%']].rename(columns={'aht': 'Site AHT'}))

    # Load Balancing Insight
    st.info(f"**Insight:** The Network Average for this task is **{network_goals[target_wf]:.2f}s**. "
            f"Sites with >100% 'Vs Network' are faster than average.")

else:
    st.info("Upload your Mercury CSV to see the Global Efficiency Index.")
