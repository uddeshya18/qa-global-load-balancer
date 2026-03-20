import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="Weekly Capacity Planner", layout="wide")

# 1. EXACT COLUMN MAPPING FROM YOUR MODEL
COLUMN_MAPPING = {
    "Column-1:Transformation Type": "workflow",
    "Column-2:Locale": "locale",
    "Column-3:Site": "site",
    "Average Handle Time(In Secs)": "aht",
    "Processed Units": "units",
}

# 2. EXACT CLEANING LOGIC FROM YOUR MODEL
def load_and_clean_data(uploaded_file):
    df = pd.read_csv(uploaded_file)
    
    # Apply your mapping
    df = df.rename(columns=COLUMN_MAPPING)
    df.columns = df.columns.str.strip()
    
    # Your specific string cleaning logic for Site/Locale/Workflow
    for col in ["site", "workflow", "locale"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            # This handles the 'nan' strings and empty cells that hide en_uk
            df = df[df[col].notna() & (df[col] != "") & (df[col] != "nan")]
    
    # Convert numeric columns
    df["aht"] = pd.to_numeric(df["aht"], errors="coerce")
    df["units"] = pd.to_numeric(df["units"], errors="coerce")
    
    # Drop rows missing AHT or Units
    df = df.dropna(subset=["aht", "units"])
    return df

# --- UI START ---
st.title("🔮 Strategic Capacity Planner")

uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type=["csv"])

if uploaded_file:
    # Trigger your logic
    df = load_and_clean_data(uploaded_file)
    
    # SIDEBAR CONTROLS
    st.sidebar.divider()
    qas_per_site = st.sidebar.number_input("QAs per Locale", min_value=1, value=10)
    prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
    growth_per_week = st.sidebar.slider("Weekly Growth %", 0, 20, 5)

    # 3. SITE & LOCALE ASSIGNMENT LOGIC (Fixed line 81)
    all_sites = sorted(df['site'].unique()) # 'site' now exists due to mapping
    selected_sites = st.sidebar.multiselect("Select Sites:", all_sites, default=all_sites)
    
    # Filter locales based on site selection
    relevant_locs = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
    selected_locales = st.sidebar.multiselect("Select Locales:", relevant_locs, default=relevant_locs)
    
    # Final Filtered DataFrame
    f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

    if f_df.empty:
        st.warning("No data found for the selected Site/Locale.")
    else:
        # Display Tabs
        tab1, tab2 = st.tabs(["📊 Historical", "🚀 Prediction"])

        with tab1:
            # Historical view showing Transformation Type (Workflow)
            hist = f_df.groupby(['locale', 'workflow']).agg({'units':'sum', 'aht':'mean'}).reset_index()
            st.dataframe(hist, use_container_width=True)

        with tab2:
            # Prediction Logic
            st.subheader("Future Capacity Forecast")
            
            # Simple Date Math
            monday = (datetime.now() + timedelta(days=(0-datetime.now().weekday()) % 7))
            week_label = st.selectbox("Forecast Week:", [f"Week {i}: {(monday + timedelta(weeks=i-1)).strftime('%d %b')}" for i in range(1,5)])
            w_idx = int(week_label.split(":")[0].split(" ")[1])

            results = []
            for (loc, wf), group in f_df.groupby(['locale', 'workflow']):
                vol = (group['units'].sum() / 11) * ((1 + (growth_per_week/100))**w_idx)
                aht_val = group['aht'].mean()
                hrs = (vol * aht_val) / 3600
                hc = hrs / (prod_hours * 5)
                
                results.append({
                    "Locale": loc,
                    "Transformation Type": wf,
                    "Exp. Vol": int(vol),
                    "HC Needed": hc,
                    "Surplus/Deficit": (qas_per_site / len(f_df[f_df['locale']==loc]['workflow'].unique())) - hc
                })
            
            st.dataframe(pd.DataFrame(results), use_container_width=True)

else:
    st.info("Upload CSV to initialize.")
