# %%
import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Global Load Balancer", layout="wide")

st.title("🌐 Global Resource & Load Balancer")
st.markdown("### Multi-Site Capacity Analytics & Cross-Locale Benchmarking")

# --- SIDEBAR: SETUP ---
st.sidebar.header("⚙️ Global Configuration")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

qas_per_site = st.sidebar.number_input("Total QAs per Site/Locale", min_value=1, value=10)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)

if uploaded_file:
    # Load data
    raw_df = pd.read_csv(uploaded_file)
    
    # 1. PRECISE MAPPING & DROPPING EXTRA FIELDS
    # Based on your image: Col 1 = Site, Col 2 = Locale, Col 4 = Workflow
    needed_cols = {
        "Column-1": "site",
        "Column-2": "locale",
        "Column-4:Transformation Type": "workflow",
        "Average Handle Time(In Secs)": "aht",
        "Processed": "units" # Taking the first 'Processed' column found
    }
    
    # Identify which columns actually exist to avoid errors
    actual_mapping = {k: v for k, v in needed_cols.items() if k in raw_df.columns}
    
    # Create the clean dataframe
    df = raw_df[list(actual_mapping.keys())].rename(columns=actual_mapping)
    
    # Convert numeric types and drop rows with missing essential data
    df['aht'] = pd.to_numeric(df['aht'], errors='coerce')
    df['units'] = pd.to_numeric(df['units'], errors='coerce')
    df = df.dropna(subset=['aht', 'units', 'workflow'])

    # 2. THE ENGINE: TRIMMED MEAN (95th Percentile)
    def get_trimmed_mean(group):
        if len(group) < 3: # If data is too thin, use the median directly
            return group.median()
        q95 = group.quantile(0.95)
        return group[group <= q95].mean()

    # Group by Locale/Site and Workflow to get the "Cleaned" Baseline
    # Using 'locale' as the primary branch identifier based on your screenshot
    aht_baselines = df.groupby(['locale', 'workflow'])['aht'].apply(get_trimmed_mean).reset_index()
    
    # 3. GLOBAL MEDIAN (Imputation for Cold-Starts)
    global_median = df['aht'].median()
    
    # 4. SITE/LOCALE COMPARISON LOGIC
    locales = df['locale'].unique()
    comparison_data = []

    for loc in locales:
        loc_df = df[df['locale'] == loc]
        loc_aht = aht_baselines[aht_baselines['locale'] == loc]
        
        # Aggregate units per workflow
        loc_summary = loc_df.groupby('workflow')['units'].sum().reset_index()
        loc_summary = loc_summary.merge(loc_aht, on='workflow', how='left')
        
        # Impute missing values
        loc_summary['aht'] = loc_summary['aht'].fillna(global_median)
        
        total_hours = (loc_summary['units'] * loc_summary['aht']).sum() / 3600
        total_capacity = qas_per_site * prod_hours * 5 # 5-day week
        utilization = (total_hours / total_capacity) * 100
        spare_hours = total_capacity - total_hours
        
        comparison_data.append({
            "Locale": loc,
            "Site": loc_df['site'].iloc[0], # Shows the associated Site (AMS, CBG, etc)
            "Total Units": int(loc_df['units'].sum()),
            "Required Hours": round(total_hours, 1),
            "Utilization %": round(utilization, 1),
            "Spare Man-Days": round(spare_hours / prod_hours, 1)
        })

    # --- UI: DASHBOARD ---
    report_df = pd.DataFrame(comparison_data)

    col1, col2, col3 = st.columns(3)
    col1.metric("Active Locales", len(locales))
    col2.metric("Network Utilization", f"{report_df['Utilization %'].mean():.1f}%")
    col3.metric("Total Spare Man-Days", f"{report_df['Spare Man-Days'].sum():.1f}")

    st.divider()

    # Comparison Table
    st.subheader("📊 Cross-Locale Capacity Overview")
    
    def highlight_util(s):
        return ['background-color: #ffcccc' if v > 100 else 'background-color: #ccffcc' for v in s]

    st.dataframe(report_df.style.apply(highlight_util, subset=['Utilization %']), use_container_width=True)

    # Efficiency Benchmarking Chart
    st.divider()
    st.subheader("📉 Efficiency Benchmark: Target vs. Actual")
    selected_wf = st.selectbox("Select Workflow to Analyze:", df['workflow'].unique())
    
    wf_bench = aht_baselines[aht_baselines['workflow'] == selected_wf]
    if not wf_bench.empty:
        st.bar_chart(wf_bench.set_index('locale')['aht'])
        st.caption(f"Comparison of 'Cleaned' AHT for {selected_wf} across locales.")

else:
    st.info("Please upload the Mercury CSV to initialize the Global Load Balancer.")

# %%



