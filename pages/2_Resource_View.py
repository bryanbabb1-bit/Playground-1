"""Page 2: Resource View — Per-consultant drilldown."""

import streamlit as st
import pandas as pd
from datetime import date

from src.metrics import trailing_avg_utilization, current_week_start
from src.charts import consultant_weekly_breakdown
from src.data_loader import get_project_history

st.title("Resource View")

consultants = st.session_state.get("consultants", [])
raw_df = st.session_state.get("raw_df", pd.DataFrame())
weekly_util = st.session_state.get("weekly_util", pd.DataFrame())
selected_consultants = st.session_state.get("selected_consultants", [])

if not consultants:
    st.warning("No data loaded.")
    st.stop()

real_consultants = [c for c in consultants if c.name.lower() != "consultant" and c.name in selected_consultants]

# Consultant selector
consultant_name = st.selectbox(
    "Select Consultant",
    options=[c.name for c in real_consultants],
)

if not consultant_name:
    st.stop()

consultant = next((c for c in real_consultants if c.name == consultant_name), None)
if not consultant:
    st.stop()

# --- Summary Card ---
cw = current_week_start()
current_forecast = consultant.forecast_hours.get(cw, 0)
current_billable = consultant.actual_billable_hours.get(cw, 0)
trailing_util = trailing_avg_utilization(consultant, weeks=4)

col1, col2, col3, col4 = st.columns(4)
col1.metric("This Week (Forecast)", f"{current_forecast:.0f} hrs")
col2.metric("This Week (Actual Billable)", f"{current_billable:.0f} hrs")
col3.metric("Current Utilization", f"{(current_forecast / 40 * 100):.0f}%" if current_forecast else "0%")
col4.metric("Trailing 4-Week Avg Util", f"{trailing_util * 100:.0f}%")

st.markdown("---")

# --- Weekly Hours Breakdown ---
st.subheader("Weekly Hours Breakdown")
if not weekly_util.empty:
    fig = consultant_weekly_breakdown(consultant_name, weekly_util)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No timecard data available.")

st.markdown("---")

# --- Forecast vs Actual ---
st.subheader("Forecast vs Actual Hours")
if consultant.forecast_hours and consultant.actual_total_hours:
    forecast_weeks = sorted(consultant.forecast_hours.keys())
    actual_weeks = sorted(consultant.actual_total_hours.keys())
    all_weeks = sorted(set(forecast_weeks) | set(actual_weeks))

    comparison_data = []
    for wk in all_weeks:
        comparison_data.append({
            "Week": pd.Timestamp(wk),
            "Forecasted": consultant.forecast_hours.get(wk, 0),
            "Actual Total": consultant.actual_total_hours.get(wk, 0),
            "Actual Billable": consultant.actual_billable_hours.get(wk, 0),
        })

    comp_df = pd.DataFrame(comparison_data)

    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=comp_df["Week"], y=comp_df["Forecasted"],
                             name="Forecasted", line=dict(color="#636EFA", dash="dash")))
    fig.add_trace(go.Scatter(x=comp_df["Week"], y=comp_df["Actual Total"],
                             name="Actual Total", line=dict(color="#EF553B")))
    fig.add_trace(go.Scatter(x=comp_df["Week"], y=comp_df["Actual Billable"],
                             name="Actual Billable", line=dict(color="#00CC96")))
    fig.update_layout(xaxis_title="Week", yaxis_title="Hours", height=400, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
elif consultant.forecast_hours:
    st.info("Only forecast data available (no actuals yet).")

st.markdown("---")

# --- Project History ---
st.subheader("Project History")
if not raw_df.empty:
    project_hist = get_project_history(raw_df)
    person_projects = project_hist[project_hist["Resource"] == consultant_name]

    if not person_projects.empty:
        display_df = person_projects[["Project", "total_hours", "billable_hours", "is_billable", "weeks_on_project"]].copy()
        display_df.columns = ["Project", "Total Hours", "Billable Hours", "Billable?", "Weeks"]
        display_df["Billable?"] = display_df["Billable?"].map({1: "Yes", 0: "No"})
        display_df = display_df.sort_values("Total Hours", ascending=False)
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No project history found for this consultant.")
else:
    st.info("No raw data available.")
