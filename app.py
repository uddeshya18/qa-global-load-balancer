import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Capacity Planner", layout="wide")

# ---------------------------------------------------------------------------
# UNIVERSAL DATA LOADING
# ---------------------------------------------------------------------------
def load_and_clean_data(uploaded_file):
    df = pd.read_csv(uploaded_file)
    df.columns = [str(c).strip() for c in df.columns]
    
    with st.expander("🔍 System Diagnostic"):
        st.write("Headers Detected:", list(df.columns))
        st.dataframe(df.head(3))

    new_df = pd.DataFrame()
    
    def find_col(keywords):
        for col in df.columns:
            if any(k.lower() in col.lower() for k in keywords):
                return col
        return None

    # Mapping based on your screenshot and requirements
    site_col = find_col(["Column-1", "Site"])
    loc_col = find_col(["Column-2", "Locale"])
    wf_col = find_col(["Transformation", "Workflow", "Column-4"])
    proc_col = find_col(["Processed"])
    aht_col = find_col(["Average Handle Time", "AHT"])

    if site_col: new_df["site"] = df[site_col].astype(str).str.strip()
    if loc_col: new_df["locale"] = df[loc_col].astype(str).str.strip()
    if wf_col: new_df["workflow"] = df[wf_col].astype(str).str.strip()
    
    # Numeric values with fillna(0) to prevent locales from disappearing
    if proc_col: new_df["units"] = pd.to_numeric(df[proc_col], errors='coerce').fillna(0)
    if aht_col: new_df["aht"] = pd.to_numeric(df[aht_col], errors='coerce').fillna(0)

    # Remove 'nan' strings which are common in Mercury CSV exports
    for col in ["site", "locale", "workflow"]:
        if col in new_df.columns:
            new_df = new_df[new_df[col].str.lower() != "nan"]
            new_df = new_df[new_df[col] != ""]
            
    return new_df

# ---------------------------------------------------------------------------
# MAIN UI
# ---------------------------------------------------------------------------
st.title("🔮 Capacity Planner & Load Balancer")

uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type=["csv"])

if uploaded_file:
    df = load_and_clean_data(uploaded_file)
    
    if not df.empty:
        # SIDEBAR INPUTS
        st.sidebar.divider()
        qas_per_site = st.sidebar.number_input("Target QAs per Locale", min_value=1, value=10)
        prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
        growth_per_week = st.sidebar.slider("Weekly Growth (%)", 0, 20, 5)

        # CASCADING FILTERS
        all_sites = sorted(df['site'].unique())
        selected_sites = st.sidebar.multiselect("1. Select Sites:", all_sites, default=all_sites)
        
        # Determine locales linked to selected sites
        site_mask = df['site'].isin(selected_sites)
        relevant_locs = sorted(df[site_mask]['locale'].unique())
        selected_locales = st.sidebar.multiselect("2. Select Locales:", relevant_locs, default=relevant_locs)
        
        # Filter Data
        f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

        if f_df.empty:
            st.warning("No data found for selected filters.")
        else:
            tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Future Prediction"])

            with tab1:
                st.subheader("Historical Workflow Statistics")
                # Locale and Workflow kept as separate columns
                summary = f_df.groupby(['locale', 'workflow']).agg({'units':'sum', 'aht':'mean'}).reset_index()
                summary['Avg Weekly Vol'] = (summary['units'] / 11).astype(int)
                st.dataframe(summary.style.format({'aht': '{:.1f}'}), use_container_width=True)

            with tab2:
                st.subheader("Future Capacity Forecast")
                
                # IMPROVED WEEK SELECTION (Start Date - End Date)
                today = datetime.now()
                monday = today + timedelta(days=(0 - today.weekday()) % 7)
                if monday <= today: monday += timedelta(days=7)
                
                week_options = []
                for i in range(1, 5):
                    start_date = monday + timedelta(weeks=i-1)
                    end_date = start_date + timedelta(days=4) # Friday
                    week_label = f"Week {i}: {start_date.strftime('%d %b')} - {end_date.strftime('%d %b')}"
                    week_options.append(week_label)
                
                selected_week = st.selectbox("Select Prediction Horizon (Mon-Fri):", week_options)
                w_idx = int(selected_week.split(":")[0].split(" ")[1])

                results = []
                # Separate columns in calculation loop
                for (loc, wf), group in f_df.groupby(['locale', 'workflow']):
                    base_vol = group['units'].sum() / 11
                    vol = base_vol * ((1 + (growth_per_week/100))**w_idx)
                    aht_val = group['aht'].mean()
                    
                    hrs = (vol * aht_val) / 3600 if aht_val > 0 else 0
                    hc = hrs / (prod_hours * 5) if prod_hours > 0 else 0
                    
                    # Count workflows in THIS locale to distribute QAs
                    wf_count = len(f_df[f_df['locale'] == loc]['workflow'].unique())
                    
                    results.append({
                        "Locale": loc,
                        "Transformation Type": wf,
                        "Exp. Volume": int(vol),
                        "HC Needed": hc,
                        "Surplus/Deficit": (qas_per_site / wf_count) - hc
                    })
                
                res_df = pd.DataFrame(results)
                
                # Final Table Display (Locale and Workflow as separate columns)
                st.dataframe(
                    res_df.style.map(
                        lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', 
                        subset=['Surplus/Deficit']
                    ).format({'HC Needed': '{:.2f}', 'Surplus/Deficit': '{:.2f}'}),
                    use_container_width=True
                )
    else:
        st.error("Data failed to load. Check Diagnostic expander.")
else:
    st.info("Upload Mercury CSV to begin.")
