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

