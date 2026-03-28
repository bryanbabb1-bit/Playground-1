"""Page 1: Dashboard Overview — Demand vs Capacity, Utilization Heatmap, Trends."""

import streamlit as st
import pandas as pd
from datetime import date

from src.metrics import (
    build_demand_capacity_df,
    build_utilization_heatmap_data,
    team_utilization_current,
    ftes_available_current,
    open_demand_hours,
    weeks_until_overcapacity,
)
from src.charts import (
    demand_vs_capacity_chart,
    utilization_heatmap,
    team_util_trend_chart,
)

st.title("Dashboard")

# Get data from session state
consultants = st.session_state.get("consultants", [])
snapshots = st.session_state.get("snapshots", [])
week_dates = st.session_state.get("week_dates", [])
selected_consultants = st.session_state.get("selected_consultants", [])
date_start = st.session_state.get("date_start", date(2024, 1, 1))
date_end = st.session_state.get("date_end", date(2027, 1, 1))

if not consultants or not snapshots:
    st.warning("No data loaded. Return to the main page to configure data sources.")
    st.stop()

# --- KPI Cards ---
col1, col2, col3, col4 = st.columns(4)

util = team_utilization_current(snapshots)
ftes = ftes_available_current(snapshots)
demand = open_demand_hours(consultants, snapshots)
overcap = weeks_until_overcapacity(snapshots)

col1.metric("Team Utilization", f"{util * 100:.1f}%" if util else "N/A")
col2.metric("FTEs Available", f"{ftes:.1f}")
col3.metric("Open Demand (hrs)", f"{demand:.0f}")
col4.metric("Weeks to Over-Capacity", f"{overcap}" if overcap is not None else "N/A")

st.markdown("---")

# --- Filter snapshots by date range ---
filtered_snapshots = [
    s for s in snapshots
    if date_start <= s.week_start <= date_end
]

# --- Demand vs Capacity Chart ---
dc_df = build_demand_capacity_df(filtered_snapshots)
if not dc_df.empty:
    st.plotly_chart(demand_vs_capacity_chart(dc_df), use_container_width=True)

st.markdown("---")

# --- Utilization Heatmap ---
filtered_weeks = [d for d in week_dates if date_start <= d <= date_end]
filtered_consultants = [c for c in consultants if c.name in selected_consultants]

heatmap_df = build_utilization_heatmap_data(filtered_consultants, filtered_weeks)
if not heatmap_df.empty:
    st.plotly_chart(utilization_heatmap(heatmap_df), use_container_width=True)
else:
    st.info("No utilization data available for the selected filters.")

st.markdown("---")

# --- Team Utilization Trend ---
if not dc_df.empty:
    st.plotly_chart(team_util_trend_chart(dc_df), use_container_width=True)

# --- Consultant Forecast Table ---
st.markdown("### Consultant Forecast Summary (Current Period)")
if filtered_consultants and filtered_weeks:
    # Show a summary table of the next 8 weeks
    from src.metrics import current_week_start
    cw = current_week_start()
    upcoming_weeks = sorted([w for w in filtered_weeks if w >= cw])[:8]

    if upcoming_weeks:
        table_data = []
        for c in filtered_consultants:
            row = {"Consultant": c.name}
            for wk in upcoming_weeks:
                row[wk.strftime("%m/%d")] = c.forecast_hours.get(wk, 0)
            avg_hours = sum(c.forecast_hours.get(wk, 0) for wk in upcoming_weeks) / len(upcoming_weeks)
            row["Avg Hours"] = round(avg_hours, 1)
            row["Avg Util %"] = f"{(avg_hours / 40 * 100):.0f}%"
            table_data.append(row)

        summary_df = pd.DataFrame(table_data)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
