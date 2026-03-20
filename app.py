import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Capacity Planner", layout="wide")

# ---------------------------------------------------------------------------
# INTEGRATED COLUMN MAPPING (From Efficiency Tool)
# ---------------------------------------------------------------------------
COLUMN_MAPPING = {
    "Column-1:Transformation Type": "workflow",
    "Column-2:Locale": "locale",
    "Column-3:Site": "site",
    "Average Handle Time(In Secs)": "aht",
    "Processed Units": "units",
}

# ---------------------------------------------------------------------------
# INTEGRATED DATA LOADING & CLEANING (From Efficiency Tool)
# ---------------------------------------------------------------------------
def load_and_clean_data(uploaded_file):
    df = pd.read_csv(uploaded_file)
    
    # Rename columns using your specific mapping
    df = df.rename(columns=COLUMN_MAPPING)
    df.columns = df.columns.str.strip()
    
    # Clean strings - This fixes the 'en_uk' and 'CBG' mismatch issues
    for col in ["site", "workflow", "locale"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            # Remove null-like strings
            df = df[df[col].notna() & (df[col] != "") & (df[col] != "nan")]
    
    # Convert numeric columns
    df["aht"] = pd.to_numeric(df["aht"], errors="coerce")
    df["units"] = pd.to_numeric(df["units"], errors="coerce")
    
    # Drop invalid rows and ensure volume exists
    df = df.dropna(subset=["aht", "units"])
    df = df[df["units"] > 0].copy()
    
    return df

# ---------------------------------------------------------------------------
# UI HELPERS
# ---------------------------------------------------------------------------
def get_trimmed_mean(group):
    """95th Percentile Trimmed Mean to remove outliers."""
    if len(group) < 5: return group.mean() if not group.empty else 0
    return group[group <= group.quantile(0.95)].mean()

def get_next_monday(d):
    days_ahead = 0 - d.weekday()
    if days_ahead <= 0: days_ahead += 7
    return d + timedelta(days_ahead)

# ---------------------------------------------------------------------------
# MAIN APP
# ---------------------------------------------------------------------------
st.title("🔮 Strategic Capacity Planner")
st.markdown("### Powered by Efficiency Index Logic")

# Sidebar
st.sidebar.header("⚙️ Configuration")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type=["csv"])

if uploaded_file:
    # Use the logic you provided
    df = load_and_clean_data(uploaded_file)
    
    # Global Settings
    st.sidebar.divider()
    qas_per_site = st.sidebar.number_input("Target QAs per Locale", min_value=1, value=10)
    prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
    growth_per_week = st.sidebar.slider("Weekly Volume Growth (%)", 0, 20, 5)

    # Filtering (Using your specific site/locale naming)
    all_sites = sorted(df['site'].unique())
    selected_sites = st.sidebar.multiselect("Select Sites:", all_sites, default=all_sites)
    
    relevant_locs = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
    selected_locales = st.sidebar.multiselect("Select Locales:", relevant_locs, default=relevant_locs)
    
    f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

    if f_df.empty:
        st.error("No data found for the selected Site/Locale combo.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Future Prediction"])

        with tab1:
            st.subheader("Historical Performance (Workflow Level)")
            # Grouping by both Locale and Workflow as requested
            hist_wf = f_df.groupby(['locale', 'workflow']).agg({
                'units': 'sum', 
                'aht': get_trimmed_mean
            }).reset_index()
            
            hist_wf['Avg Weekly Units'] = (hist_wf['units'] / 11).astype(int)
            st.dataframe(hist_wf.style.format({'aht': '{:.1f}'}), use_container_width=True)

        with tab2:
            st.subheader("Weekly Capacity Forecast")
            
            # Forecast Dates
            start_monday = get_next_monday(datetime.now())
            week_options = [f"Week {i}: {(start_monday + timedelta(weeks=i-1)).strftime('%d %b')}" for i in range(1, 5)]
            selected_week = st.selectbox("Forecast Horizon:", week_options)
            week_idx = int(selected_week.split(":")[0].split(" ")[1])
            
            # Calculation Engine
            pred_data = []
            for (loc, wf), group in f_df.groupby(['locale', 'workflow']):
                # Growth Math
                base_weekly_vol = group['units'].sum() / 11
                growth_multiplier = (1 + (growth_per_week / 100)) ** week_idx
                pred_vol = base_weekly_vol * growth_multiplier
                
                # AHT Math
                aht_val = get_trimmed_mean(group['aht'])
                
                # Capacity Math
                req_hours = (pred_vol * aht_val) / 3600
                hc_needed = req_hours / (prod_hours * 5)
                
                pred_data.append({
                    "Locale": loc,
                    "Transformation Type": wf,
                    "Exp. Volume": int(pred_vol),
                    "Cleaned AHT": aht_val,
                    "Req. Hours": req_hours,
                    "HC Needed": hc_needed
                })

            res_df = pd.DataFrame(pred_data)
            
            # Aggregate to Locale level for the "Surplus/Deficit" view
            locale_summary = res_df.groupby("Locale").agg({
                "Exp. Volume": "sum",
                "Req. Hours": "sum",
                "HC Needed": "sum"
            }).reset_index()
            
            locale_summary["Utilization %"] = (locale_summary["HC Needed"] / qas_per_site) * 100
            locale_summary["Surplus/Deficit"] = qas_per_site - locale_summary["HC Needed"]

            st.write("### 📍 Locale Staffing Status")
            st.dataframe(
                locale_summary.style.map(
                    lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', 
                    subset=['Surplus/Deficit']
                ).format({'Utilization %': '{:.1f}%', 'HC Needed': '{:.1f}', 'Surplus/Deficit': '{:.1f}', 'Req. Hours': '{:.1f}'}),
                use_container_width=True
            )

            st.write("### 🛠️ Transformation Type Breakdown")
            st.dataframe(
                res_df.style.format({'Cleaned AHT': '{:.1f}', 'Req. Hours': '{:.1f}', 'HC Needed': '{:.1f}'}),
                use_container_width=True
            )

else:
    st.info("Please upload the Mercury Data CSV (formatted with Column-1 through Column-6).")
