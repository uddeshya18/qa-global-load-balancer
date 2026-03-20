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

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file)
    
    # 1. MANUAL COLUMN OVERRIDE (In case auto-detection fails)
    st.sidebar.subheader("🛠️ Column Mapping")
    all_cols = list(raw_df.columns)
    
    # Try to auto-find, but allow user to change
    def auto_find(keys, cols):
        for k in keys:
            for c in cols:
                if k.lower() in c.lower(): return c
        return cols[0]

    sel_site = st.sidebar.selectbox("Site Column:", all_cols, index=all_cols.index(auto_find(["Column-1", "Site"], all_cols)))
    sel_loc = st.sidebar.selectbox("Locale Column:", all_cols, index=all_cols.index(auto_find(["Column-2", "Locale"], all_cols)))
    sel_wf = st.sidebar.selectbox("Workflow Column:", all_cols, index=all_cols.index(auto_find(["Column-4", "Transformation"], all_cols)))
    sel_aht = st.sidebar.selectbox("AHT Column:", all_cols, index=all_cols.index(auto_find(["AHT", "Handle Time"], all_cols)))
    sel_units = st.sidebar.selectbox("Units Column:", all_cols, index=all_cols.index(auto_find(["Processed", "Units"], all_cols)))

    # 2. DATA PROCESSING
    df = raw_df[[sel_site, sel_loc, sel_wf, sel_aht, sel_units]].copy()
    df.columns = ['site', 'locale', 'workflow', 'aht', 'units']
    
    # Clean Strings (Force en_uk and CBG to match)
    df['site'] = df['site'].fillna("UNKNOWN").astype(str).str.strip().str.upper()
    df['locale'] = df['locale'].fillna("UNKNOWN").astype(str).str.strip().str.lower()
    df['workflow'] = df['workflow'].fillna("GENERAL").astype(str).str.strip()
    
    # Clean Numbers
    df['aht'] = pd.to_numeric(df['aht'], errors='coerce').fillna(0)
    df['units'] = pd.to_numeric(df['units'], errors='coerce').fillna(0)

    # 3. GLOBAL FILTERS
    st.sidebar.divider()
    qas_per_site = st.sidebar.number_input("Current QAs per Locale", min_value=1, value=10)
    prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
    growth_per_week = st.sidebar.slider("Weekly Volume Growth (%)", 0, 20, 5)

    all_sites = sorted(df['site'].unique())
    selected_sites = st.sidebar.multiselect("Filter Sites:", all_sites, default=all_sites)
    
    relevant_locs = sorted(df[df['site'].isin(selected_sites)]['locale'].unique())
    selected_locales = st.sidebar.multiselect("Filter Locales:", relevant_locs, default=relevant_locs)
    
    f_df = df[(df['site'].isin(selected_sites)) & (df['locale'].isin(selected_locales))]

    # Trimmed Mean Logic
    def get_trimmed_mean(group):
        clean = group[group > 0]
        if len(clean) < 5: return clean.mean() if not clean.empty else 0
        return clean[clean <= clean.quantile(0.95)].mean()

    if f_df.empty:
        st.warning("⚠️ No data matches the selected filters.")
    else:
        tab1, tab2 = st.tabs(["📊 Historical Audit", "🚀 Future Prediction"])

        with tab1:
            st.subheader("Historical Performance (Jan 1 - Mar 18)")
            # Summary Table
            hist_sum = f_df.groupby(['locale', 'workflow']).agg({'units': 'sum', 'aht': get_trimmed_mean}).reset_index()
            hist_sum['Avg Weekly Units'] = (hist_sum['units'] / 11).astype(int)
            st.dataframe(hist_sum.style.format({'aht': '{:.1f}'}), use_container_width=True)

        with tab2:
            st.subheader("Weekly Workflow Prediction")
            
            # Date Logic
            def get_next_monday(d):
                days_ahead = 0 - d.weekday()
                if days_ahead <= 0: days_ahead += 7
                return d + timedelta(days_ahead)
            
            monday = get_next_monday(datetime.now())
            week_opts = [f"Week {i}: {(monday + timedelta(weeks=i-1)).strftime('%d %b')}" for i in range(1, 5)]
            selected_week = st.selectbox("Select Week:", week_opts)
            w_idx = int(selected_week.split(":")[0].split(" ")[1])

            # Prediction Math
            pred_results = []
            for (loc, wf), group in f_df.groupby(['locale', 'workflow']):
                base_vol = group['units'].sum() / 11
                growth = (1 + (growth_per_week / 100)) ** w_idx
                p_vol = base_vol * growth
                p_aht = get_trimmed_mean(group['aht'])
                
                req_hrs = (p_vol * p_aht) / 3600
                hc = req_hrs / (prod_hours * 5)
                
                pred_results.append({
                    "Locale": loc,
                    "Transformation Type": wf,
                    "Exp. Volume": int(p_vol),
                    "Req. Prod Hours": req_hrs,
                    "HC Needed": hc,
                    "Surplus/Deficit": (qas_per_site / len(f_df[f_df['locale']==loc]['workflow'].unique())) - hc
                })

            res_df = pd.DataFrame(pred_results)
            
            st.write("### 📍 Operational Breakdown")
            st.dataframe(
                res_df.style.map(lambda x: 'background-color: #ffcccc' if x < 0 else 'background-color: #ccffcc', subset=['Surplus/Deficit'])
                .format({'Req. Prod Hours': '{:.1f}', 'HC Needed': '{:.1f}', 'Surplus/Deficit': '{:.1f}'}),
                use_container_width=True
            )

else:
    st.info("Upload CSV to start.")
