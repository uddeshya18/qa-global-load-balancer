import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Capacity Planner", layout="wide")

# ---------------------------------------------------------------------------
# UNIVERSAL SEARCH & LOAD (Keyword-Based)
# ---------------------------------------------------------------------------
def load_and_clean_data(uploaded_file):
    # Load raw data
    df = pd.read_csv(uploaded_file)
    
    # Standardize all column names to string and strip spaces
    df.columns = [str(c).strip() for c in df.columns]
    
    # DIAGNOSTIC: Show the user what the AI sees
    with st.expander("🔍 System Diagnostic - Column Mapping"):
        st.write("Headers detected in your CSV:", list(df.columns))
        st.write("Preview of Top Rows:", df.head(3))

    new_df = pd.DataFrame()
    
    # HELPER: Find column by keyword
    def find_col(keywords):
        for col in df.columns:
            if any(k.lower() in col.lower() for k in keywords):
                return col
        return None

    # --- DYNAMIC MAPPING ---
    # 1. Find Site (Looking for 'Column-1', 'Site', or 'Location')
    site_col = find_col(["Column-1", "Site", "Location"])
    if site_col: new_df["site"] = df[site_col].astype(str).str.strip()
    
    # 2. Find Locale (Looking for 'Column-2', 'Locale', 'Language')
    loc_col = find_col(["Column-2", "Locale", "Language"])
    if loc_col: new_df["locale"] = df[loc_col].astype(str).str.strip()
    
    # 3. Find Workflow (Looking for 'Transformation', 'Workflow', 'Task')
    wf_col = find_col(["Transformation", "Workflow", "Column-4"])
    if wf_col: new_df["workflow"] = df[wf_col].astype(str).str.strip()
    
    # 4. Find Units (Looking for 'Processed')
    proc_col = find_col(["Processed"])
    if proc_col: new_df["units"] = pd.to_numeric(df[proc_col], errors='coerce').fillna(0)
    
    # 5. Find AHT (Looking for 'Average Handle Time')
    aht_col = find_col(["Average Handle Time", "AHT"])
    if aht_col: new_df["aht"] = pd.to_numeric(df[aht_col], errors='coerce').fillna(0)

    # --- FINAL VALIDATION ---
    # Ensure mandatory columns exist
    required = ["site", "locale", "workflow", "units", "aht"]
    missing = [r for r in required if r not in new_df.columns]
    
    if missing:
        st.error(f"❌ Missing critical columns: {missing}")
        return pd.DataFrame()

    # Drop "nan" strings (Empty cells in Mercury CSVs often become 'nan' text)
    for col in ["site", "locale", "workflow"]:
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

        # --- CASCADING FILTERS (THE KEY FIX) ---
        # Step 1: Filter Site
        all_sites = sorted(df['site'].unique())
        selected_sites = st.sidebar.multiselect("1. Select Sites:", all_sites, default=all_sites)
        
        # Step 2: Filter Locales based ON the selected Sites
        site_filtered_df = df[df['site'].isin(selected_sites)]
        relevant_locs = sorted(site_filtered_df['locale'].unique())
        
        # Step 3: Select Locales - en_uk should now appear here
        selected_locales = st.sidebar.multiselect("2. Select Locales:", relevant_locs, default=relevant_locs)
        
        # Final DataFrame for display
        f_df = site_filtered_df[site_filtered_df['locale'].isin(selected_locales)]

        if f_df.empty:
            st.warning("No data found for the selected Site/Locale combo.")
        else:
            tab1, tab2 = st.tabs(["📊 Audit View", "🚀 Forecast View"])

            with tab1:
                st.subheader("Historical Workflow Statistics")
                summary = f_df.groupby(['locale', 'workflow']).agg({'units':'sum', 'aht':'mean'}).reset_index()
                summary['Avg Weekly Vol'] = (summary['units'] / 11).astype(int)
                st.dataframe(summary.style.format({'aht': '{:.1f}'}), use_container_width=True)

            with tab2:
                st.subheader("Future Capacity Forecast")
                
                # Monday Calculation
                today = datetime.now()
                monday = today + timedelta(days=(0 - today.weekday()) % 7)
                if monday <= today: monday += timedelta(days=7)
                
                week_opts = [f"Week {i}: {(monday + timedelta(weeks=i-1)).strftime('%d %b')}" for i in range(1, 5)]
                selected_week = st.selectbox("Select Prediction Week:", week_opts)
                w_idx = int(selected_week.split(":")[0].split(" ")[1])

                results = []
                for (loc, wf), group in f_df.groupby(['locale', 'workflow']):
                    # Prediction Calculation
                    vol = (group['units'].sum() / 11) * ((1 + (growth_per_week/100))**w_idx)
                    aht_val = group['aht'].mean()
                    hrs = (vol * aht_val) / 3600 if aht_val > 0 else 0
                    hc = hrs / (prod_hours * 5) if prod_hours > 0 else 0
                    
                    # Logic for Surplus
                    wf_count = len(f_df[f_df['locale'] == loc]['workflow'].unique())
                    results.append({
                        "Locale": loc,
                        "Transformation Type": wf,
                        "Exp. Volume": int(vol),
                        "HC Needed": hc,
                        "Surplus/Deficit": (qas_per_site / wf_count) - hc
                    })
                
                res_df = pd.DataFrame(results)
                st.dataframe(
                    res_df.style.map(lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', subset=['Surplus/Deficit'])
                    .format({'HC Needed': '{:.2f}', 'Surplus/Deficit': '{:.2f}'}),
                    use_container_width=True
                )
    else:
        st.error("Data processing failed. Check the 'System Diagnostic' expander above.")
else:
    st.info("Upload the Mercury CSV to initialize. Logic: Site -> Locale -> Transformation Type.")
