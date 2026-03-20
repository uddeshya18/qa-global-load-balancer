import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Global Performance Engine", layout="wide")

st.title("📊 Global Performance & Efficiency Engine")
st.markdown("### Advanced Multi-Filter & Task Benchmarking")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Global Controls")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

qas_per_site = st.sidebar.number_input("Average QAs per Locale", min_value=1, value=10)
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

    # Create Clean DF
    df = raw_df[[col_site, col_locale, col_wf, col_aht, col_units]].copy()
    df.columns = ['site', 'locale', 'workflow', 'aht', 'units']
    df['aht'] = pd.to_numeric(df['aht'], errors='coerce')
    df['units'] = pd.to_numeric(df['units'], errors='coerce')
    df = df.dropna(subset=['aht', 'units'])

    # 2. DYNAMIC FILTERS (The "Drill-Down" Feature)
    st.sidebar.divider()
    st.sidebar.subheader("🔍 Filter Dashboard")
    
    selected_site = st.sidebar.multiselect("Select Site(s):", options=df['site'].unique(), default=df['site'].unique())
    
    # Locale filter updates based on Site selection
    available_locales = df[df['site'].isin(selected_site)]['locale'].unique()
    selected_locale = st.sidebar.multiselect("Select Locale(s):", options=available_locales, default=available_locales)
    
    # Workflow filter updates based on Locale selection
    available_wfs = df[df['locale'].isin(selected_locale)]['workflow'].unique()
    selected_wf = st.sidebar.selectbox("Benchmark Specific Workflow:", options=["All Workflows"] + list(available_wfs))

    # Apply Filters to the Data
    filtered_df = df[(df['site'].isin(selected_site)) & (df['locale'].isin(selected_locale))]
    if selected_wf != "All Workflows":
        filtered_df = filtered_df[filtered_df['workflow'] == selected_wf]

    # 3. THE CALCULATION ENGINE
    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    # Metrics
    site_wf_perf = filtered_df.groupby(['locale', 'workflow'])['aht'].apply(get_trimmed_mean).reset_index()
    
    # 4. DASHBOARD UI
    # Top Row: Key Metrics
    total_units = filtered_df['units'].sum()
    avg_aht = filtered_df['aht'].mean()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Filtered Units", f"{int(total_units):,}")
    c2.metric("Avg AHT (Filtered)", f"{avg_aht:.1f}s")
    c3.metric("Active Locales", len(filtered_df['locale'].unique()))

    st.divider()

    # Left Column: Table | Right Column: Chart
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("📋 Performance Leaderboard")
        # Ranking locales by their average AHT for the selected view
        leaderboard = site_wf_perf.groupby('locale')['aht'].mean().sort_values().reset_index()
        leaderboard.columns = ['Locale', 'Avg Trimmed AHT (s)']
        st.table(leaderboard)

    with col_right:
        st.subheader("📈 Cross-Locale Benchmarking")
        chart_data = site_wf_perf.groupby('locale')['aht'].mean()
        st.bar_chart(chart_data)

    # 5. LOAD BALANCING INSIGHT
    st.divider()
    st.subheader("💡 Strategic Recommendation")
    if selected_wf != "All Workflows":
        best_locale = leaderboard['Locale'].iloc[0]
        st.success(f"For **{selected_wf}**, the most efficient locale is **{best_locale}**. Consider routing overflow volume here to maximize throughput.")
    else:
        st.info("Select a specific workflow in the sidebar to see detailed routing recommendations.")

else:
    st.info("Please upload your Mercury CSV to begin.")
