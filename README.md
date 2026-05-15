## 📦 Part of the Operations Excellence Suite

This repository is an independent component of a modular, three-tier ecosystem designed to handle end-to-end workforce optimization and capacity logistics:

1. **🌐 [Global Load Balancer](https://github.com/uddeshya18/ops-global-load-balancer):** Manages multi-site resource routing, high-level queue balancing, and macro-level SLA parity across diverse locales.
2. **🧮 [Workforce Capacity Engine](https://github.com/uddeshya18/workforce-capacity-engine):** Handles granular, localized micro-headcount requirements using 95th-percentile trimmed-mean AHT modeling.
3. **📈 [Demand Forecast Simulator (This Tool)](#):** Executes 4-week look-ahead predictive volume modeling and "What-If" growth scenario testing based on historical trends.

# 📊 Strategic Capacity Planner

The **Strategic Capacity Planner** is a data-driven operational engine designed to solve the "Headcount Paradox": maintaining high SLA compliance while minimizing resource waste. Built on a flexible Python backend, this tool transforms raw Mercury CSV exports into actionable 4-week workforce projections.

---

## 🏗️ Technical Sophistication

* **Dynamic Column Mapping:** Unlike rigid tools, this engine uses intelligent index scanning to identify critical data points (Site, Locale, Workflow, Units, AHT) even if the source CSV column order changes.
* **Statistical Integrity (Outlier Mitigation):** Implements a **95th-percentile trimmed mean** logic for Average Handle Time (AHT). By discarding performance anomalies, the planner ensures models are rooted in realistic, stable metrics.
* **Contextual Growth Modeling:** Features a synchronized growth engine that calculates weekly volume fluctuations, capped at **20%** to prevent unrealistic staffing spikes and floored at **0%** for safety.
* **Stateful Workforce Simulation:** Integrates user-defined constraints (Productive Hours, Baseline QAs) with historical baselines to generate real-time Surplus/Deficit reporting.

---

## 🧮 Core Resource Formula

The planning engine operates on a standardized man-day capacity model:

$$Required\ HC = \frac{(\text{Predicted Units} \times \text{Trimmed AHT}) / 3600}{\text{Daily Productive Hours} \times 5}$$

---

## 🛠️ Tech Stack

* **Frontend:** Streamlit
* **Data Processing:** Pandas, NumPy
* **Visualization:** Native Streamlit Metrics & Dataframes

