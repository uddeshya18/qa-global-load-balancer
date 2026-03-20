import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Global Predictor Engine", layout="wide")

st.title("🔮 Global Performance & Forecast Engine")
st.markdown("### Historical Benchmarking + 4-Week Capacity Projection")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Global Controls")
uploaded_file = st.sidebar.file_uploader("Upload Mercury CSV", type="csv")

qas_per_site = st.sidebar.number_input("Current QAs per Locale", min_value=1, value=10)
prod_hours = st.sidebar.slider("Daily Productive Hours", 5.0, 9.0, 7.5)
growth_buffer = st.sidebar.slider("Expected Volume Growth (%)", 0, 50, 10)

# Constants based on your data (Jan 1 - March 18)
WEEKS_IN_DATA = 11 

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

    df = raw_df[[col_site, col_locale, col_wf, col_aht, col_units]].copy()
    df.columns = ['site', 'locale', 'workflow', 'aht', 'units']
    df['aht'] = pd.to_numeric(df['aht'], errors='coerce')
    df['units'] = pd.to_numeric(df['units'], errors='coerce')
    df = df.dropna(subset=['aht', 'units'])

    # 2. CALCULATION ENGINE
    def get_trimmed_mean(group):
        if len(group) < 3: return group.median()
        return group[group <= group.quantile(0.95)].mean()

    # --- TABBED INTERFACE ---
    tab1, tab2 = st.tabs(["📊 Historical Analysis", "🚀 Future Forecasting"])

    with tab1:
        st.subheader("Q1 Performance Review (Jan 1 - Mar 18)")
        
        # Weekly Metrics
        weekly_units = df.groupby('locale')['units'].sum() / WEEKS_IN_DATA
        avg_aht = df.groupby('locale')['aht'].apply(get_trimmed_mean)
        
        hist_df = pd.DataFrame({
            "Avg Weekly Units": weekly_units.astype(int),
            "Trimmed AHT (s)": avg_aht.round(1)
        }).reset_index()
        
        st.dataframe(hist_df.sort_values("Avg Weekly Units", ascending=False), use_container_width=True)
        st.bar_chart(hist_df.set_index('locale')['Avg Weekly Units'])

    with tab2:
        st.subheader("Next 4-Week Capacity Forecast")
        st.write(f"Predicting load for March 19 - April 15 based on a **{growth_buffer}%** growth trend.")
        
        forecast_data = []
        for locale in df['locale'].unique():
            loc_data = df[df['locale'] == locale]
            
            # 1. Current Velocity
            current_weekly_units = loc_data['units'].sum() / WEEKS_IN_DATA
            
            # 2. Predicted Velocity (Current + Buffer)
            predicted_weekly_units = current_weekly_units * (1 + (growth_buffer / 100))
            
            # 3. Efficiency (AHT)
            clean_aht = get_trimmed_mean(loc_data['aht'])
            
            # 4. Required Capacity (Math: Units * AHT / 3600)
            req_hours_weekly = (predicted_weekly_units * clean_aht) / 3600
            avail_hours_weekly = qas_per_site * prod_hours * 5
            
            # 5. Headcount Gap
            hc_needed = req_hours_weekly / (prod_hours * 5)
            hc_gap = hc_needed - qas_per_site
            
            forecast_data.append({
                "Locale": locale,
                "Predicted Units/Week": int(predicted_weekly_units),
                "Req. Hours/Week": round(req_hours_weekly, 1),
                "Utilization %": round((req_hours_weekly / avail_hours_weekly) * 100, 1),
                "Headcount Needed": round(hc_needed, 1),
                "HC Gap/Surplus": round(-hc_gap, 1) # Positive means you have extra people
            })

        forecast_df = pd.DataFrame(forecast_data)
        
        # Highlighting the Red Zones
        def color_hc(val):
            color = 'red' if val < 0 else 'green'
            return f'color: {color}'

        st.table(forecast_df.style.applymap(color_hc, subset=['HC Gap/Surplus']))
        
        st.info("💡 **Interpretation:** A negative 'HC Gap' means you need to hire or move volume. A positive number means that locale can take on more work.")

else:
    st.info("Upload CSV to generate historical analysis and future capacity forecasts.")
