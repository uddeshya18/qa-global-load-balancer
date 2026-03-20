import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Capacity Planner", layout="wide")

# ---------------------------------------------------------------------------
# FIXED DATA LOADING (Corrected Variable Names & Indexing)
# ---------------------------------------------------------------------------
def load_and_clean_data(uploaded_file):
    df = pd.read_csv(uploaded_file)
    
    # Clean headers of any leading/trailing spaces
    df.columns = df.columns.str.strip()
    
    # --- DIAGNOSTIC LOG (Crucial for debugging missing locales) ---
    with st.expander("🔍 Data Diagnostic - Check here if Locales are missing"):
        st.write("Column Names Found:", list(df.columns))
        st.write("Top 5 Rows of Data:")
        st.dataframe(df.head())

    new_df = pd.DataFrame()
    
    try:
        # 1. POSITIONAL MAPPING (Safest for Mercury exports)
        # Based on screenshot: Col 0=Site, Col 1=Locale, Col 3=Workflow
        new_df["site"] = df.iloc[:, 0].astype(str).str.strip()
        new_df["locale"] = df.iloc[:, 1].astype(str).str.strip()
        new_df["workflow"] = df.iloc[:, 3].astype(str).str.strip()
        
        # 2. NAME-BASED SEARCH FOR NUMERICS (More flexible)
        # Search for 'Processed' column
        proc_cols = [c for c in df.columns if "Processed" in c]
        if proc_cols:
            new_df["units"] = df[proc_cols[0]]
        else:
            new_df["units"] = df.iloc[:, 13] # Fallback to index 13
            
        # Search for 'AHT' column
        aht_cols = [c for c in df.columns if "Average Handle Time" in c]
        if aht_cols:
            new_df["aht"] = df[aht_cols[0]]
        else:
            new_df["aht"] = df.iloc[:, 15] # Fallback to index 15
            
    except Exception as e:
        st.error(f"⚠️ Mapping Error: {e}")
        return pd.DataFrame()

    # 3. CLEANING (Keep en_uk even if data is thin)
    # Remove rows where site/locale is literally 'nan' or empty
    for col in ["site", "locale", "workflow"]:
        new_df = new_df[new_df[col].notna()]
        new_df = new_df[new_df[col].str.lower() != "nan"]
        new_df = new_df[new_df[col] != ""]

    # Convert numeric values, fill missing with 0 to keep the locale visible
    new_df["aht"] = pd.to_numeric(new_df["aht"], errors="coerce").fillna(0)
    new_df["units"] = pd.to_numeric(new_df["units"], errors="coerce").fillna(0)
    
    return new_df

# ---------------------------------------------------------------------------
# MAIN UI
# ---------------------------------------------------------------------------
st.title("🔮 Weekly Capacity Planner")

uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type=["csv"])

if uploaded_file:
    df = load_and_clean_data(uploaded_file)
    
    if not df.empty:
        # SIDEBAR PARAMETERS
        st.sidebar.divider()
        qas_per_site = st.sidebar.number_input("Target QAs per Locale", min_value=1, value=10)
        prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
        growth_per_week = st.sidebar.slider("Weekly Growth (%)", 0, 20, 5)

        # --- DYNAMIC FILTERING LOGIC ---
        # 1. Get All Sites
        all_sites = sorted(df['site'].unique())
        selected_sites = st.sidebar.multiselect("1. Select Sites:", all_sites, default=all_sites)
        
        # 2. Get Locales belonging to those Sites (This fixes the 'en_uk' visibility)
        mask_sites = df['site'].isin(selected_sites)
        relevant_locs = sorted(df[mask_sites]['locale'].unique())
        
        selected_locales = st.sidebar.multiselect("2. Select Locales:", relevant_locs, default=relevant_locs)
        
        # 3. Final Filter
        f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

        if f_df.empty:
            st.warning("No data found for selected filters.")
        else:
            tab1, tab2 = st.tabs(["📊 Historical", "🚀 Prediction"])

            with tab1:
                st.subheader("Historical Workflow Audit")
                # Group by Locale and Workflow (Transformation Type)
                summary = f_df.groupby(['locale', 'workflow']).agg({'units':'sum', 'aht':'mean'}).reset_index()
                summary['Avg Weekly Vol'] = (summary['units'] / 11).astype(int)
                st.dataframe(summary.style.format({'aht': '{:.1f}'}), use_container_width=True)

            with tab2:
                st.subheader("Future Capacity Forecast")
                
                # Date Math
                monday = (datetime.now() + timedelta(days=(0-datetime.now().weekday()) % 7))
                if monday <= datetime.now(): monday += timedelta(days=7)
                
                week_opts = [f"Week {i}: {(monday + timedelta(weeks=i-1)).strftime('%d %b')}" for i in range(1, 5)]
                selected_week = st.selectbox("Forecast Horizon:", week_opts)
                w_idx = int(selected_week.split(":")[0].split(" ")[1])

                results = []
                for (loc, wf), group in f_df.groupby(['locale', 'workflow']):
                    # Prediction Calc
                    vol = (group['units'].sum() / 11) * ((1 + (growth_per_week/100))**w_idx)
                    aht_val = group['aht'].mean()
                    hrs = (vol * aht_val) / 3600 if aht_val > 0 else 0
                    hc = hrs / (prod_hours * 5) if prod_hours > 0 else 0
                    
                    # Surplus/Deficit logic
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
        st.error("The processed data is empty. Please check the 'Data Diagnostic' above to see column indices.")

else:
    st.info("Upload Mercury CSV to initialize calculations.")
